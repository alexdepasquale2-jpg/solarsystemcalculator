"""
Balance tests: the ones that justify generating content at all.

A hand-authored game is balanced by playing it. A generated game cannot be, so
these tests play it instead -- a mediocre autoplayer, across a spread of seeds,
asserting that the *pacing envelope* holds. They are the difference between
"the generator produces valid JSON" and "the generator produces a game".

The assertions are deliberately loose. Variety is the product: a seed that
prestiges in four minutes and one that takes eight are both fine, and pinning the
median would forbid exactly the variation we want. What is asserted is that no
seed lands outside the playable envelope.

These are slower than the rest of the suite (a few seconds). That is the cost of
testing a generator rather than a function.
"""

from __future__ import annotations

import unittest

from incgame.balance import audit, simulate
from incgame.generator import generate_game

# A fixed spread rather than a random sample: a balance test that fails only
# sometimes is a balance test nobody trusts. Widen the range when tuning.
SEEDS = list(range(1, 61))
MINUTES = 12.0


class TestSingleRun(unittest.TestCase):
    def test_a_run_makes_progress(self):
        metrics = simulate(generate_game(42), seconds=MINUTES * 60)
        self.assertGreater(metrics.actions_taken, 100)
        self.assertGreater(metrics.upgrades_bought, 0)
        self.assertGreater(metrics.generators_bought, 0)
        self.assertGreater(metrics.run_score, 0)

    def test_simulation_is_reproducible(self):
        first = simulate(generate_game(42), seconds=300)
        second = simulate(generate_game(42), seconds=300)
        self.assertEqual(first.actions_taken, second.actions_taken)
        self.assertEqual(first.upgrades_bought, second.upgrades_bought)
        self.assertAlmostEqual(first.run_score, second.run_score, places=6)

    def test_idle_play_still_progresses(self):
        # Someone who never taps should still get somewhere once they own
        # generators; an incremental that requires constant input is a clicker.
        metrics = simulate(generate_game(42), seconds=1800, clicks_per_second=0.2)
        self.assertGreater(metrics.generators_bought, 0)
        self.assertGreater(metrics.run_score, 0)


class TestEnvelope(unittest.TestCase):
    """Every seed must land inside the playable envelope."""

    @classmethod
    def setUpClass(cls):
        cls.report = audit(SEEDS, seconds=MINUTES * 60)
        cls.runs = [simulate(generate_game(seed), seconds=MINUTES * 60) for seed in SEEDS]

    def test_no_seed_is_unplayable(self):
        failures = self.report["failures"]
        # A couple of outliers in sixty is acceptable and expected; a systematic
        # break is not. The message names them so a regression is actionable.
        self.assertLessEqual(
            len(failures),
            3,
            "too many unplayable seeds:\n"
            + "\n".join(f"  seed {f['seed']}: {'; '.join(f['problems'])}" for f in failures),
        )

    def test_first_upgrade_is_quick_everywhere(self):
        for metrics in self.runs:
            self.assertIsNotNone(metrics.first_upgrade_at, f"seed {metrics.seed}: no upgrade ever")
            self.assertLess(
                metrics.first_upgrade_at, 300, f"seed {metrics.seed}: first upgrade too slow"
            )

    def test_first_generator_is_quick_everywhere(self):
        for metrics in self.runs:
            self.assertIsNotNone(metrics.first_generator_at, f"seed {metrics.seed}: no generator ever")
            self.assertLess(
                metrics.first_generator_at, 300, f"seed {metrics.seed}: first generator too slow"
            )

    def test_prestige_is_reachable_but_not_instant(self):
        for metrics in self.runs:
            self.assertIsNotNone(metrics.first_prestige_at, f"seed {metrics.seed}: prestige unreachable")
            self.assertGreater(
                metrics.first_prestige_at, 45, f"seed {metrics.seed}: prestige is trivial"
            )

    def test_the_economy_goes_downstream(self):
        # A run where only the tier-0 resource is ever produced has a chain that
        # does not function, whatever the upgrade tree looks like.
        for metrics in self.runs:
            self.assertGreaterEqual(
                metrics.resources_touched, 2, f"seed {metrics.seed}: never refined anything"
            )

    def test_most_runs_do_not_exhaust_their_content(self):
        """
        A seed whose whole tree fits in twelve minutes is a short seed, not a
        broken one -- trees range from 30 to 60 upgrades, and a small tree paired
        with a fast economy is legitimate variety. What would be broken is that
        being *typical*, so this bounds the proportion rather than forbidding it.
        """
        exhausted = [m.seed for m in self.runs if m.upgrades_held >= m.upgrades]
        self.assertLess(
            len(exhausted),
            len(self.runs) * 0.15,
            f"{len(exhausted)}/{len(self.runs)} seeds ran out of upgrades: {exhausted}",
        )

    def test_typical_runs_leave_most_of_the_tree_unbought(self):
        fractions = sorted(m.upgrades_held / max(1, m.upgrades) for m in self.runs)
        median = fractions[len(fractions) // 2]
        self.assertLess(median, 0.7, f"median run buys {median:.0%} of its tree in {MINUTES:g}min")

    def test_medians_sit_in_a_sane_band(self):
        medians = self.report["medians"]
        self.assertLess(medians["first_upgrade_at"], 60)
        self.assertLess(medians["first_generator_at"], 90)
        self.assertGreater(medians["first_prestige_at"], 90)
        self.assertLess(medians["first_prestige_at"], 900)

    def test_prestige_timing_does_not_depend_on_chain_depth(self):
        """
        Deep and shallow economies must prestige on comparable timescales.

        Run score weights resources by 10^tier, so without the depth-scaled
        divisor a five-tier seed reached prestige in under a minute while a
        two-tier seed took ten. Same number, two different games. This is the
        regression test for that scaling.
        """
        by_depth: dict = {}
        for metrics in self.runs:
            if metrics.first_prestige_at is not None:
                by_depth.setdefault(metrics.max_tier, []).append(metrics.first_prestige_at)
        depths = {d: sum(v) / len(v) for d, v in by_depth.items() if len(v) >= 3}
        if len(depths) < 2:
            self.skipTest("not enough depth variety in this seed range")
        spread = max(depths.values()) / max(1e-9, min(depths.values()))
        self.assertLess(spread, 6.0, f"prestige timing varies {spread:.1f}x across depths: {depths}")


class TestMechanicCoverage(unittest.TestCase):
    def test_all_mechanic_kinds_are_exercised(self):
        frequency = audit(list(range(1, 41)), seconds=120)["mechanic_frequency"]
        self.assertGreaterEqual(len(frequency), 5, f"only saw {sorted(frequency)}")

    def test_upkeep_throttling_actually_happens(self):
        # Throttling is the main source of mid-run tension. If no seed in a wide
        # sample ever starves a generator, the mechanic is decorative.
        throttled = sum(
            1 for seed in range(1, 41) if simulate(generate_game(seed), seconds=900).throttled_generators
        )
        self.assertGreater(throttled, 0, "no seed ever starved a generator")


if __name__ == "__main__":
    unittest.main()
