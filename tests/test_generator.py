"""
Generation invariants.

These tests do not check that any particular seed produces any particular game --
that would be asserting the output of a random number generator, which is a test
that fails the moment you improve anything. They check the properties that must
hold for *every* seed, because a violated property is a soft-locked run and a
soft-locked run is indistinguishable from a crash to a player.

Written for stdlib unittest so `python -m unittest` works with no dependencies;
pytest picks them up unchanged.
"""

from __future__ import annotations

import unittest
from dataclasses import replace

from incgame.generator import InvalidGame, generate_game, validate_game
from incgame.model import Unlock

# Enough seeds to catch a property that only breaks on unusual chain shapes,
# few enough to keep the suite under a couple of seconds.
SEEDS = list(range(1, 121))


class TestDeterminism(unittest.TestCase):
    def test_same_seed_gives_identical_game(self):
        for seed in (1, 42, 999, 2**30):
            with self.subTest(seed=seed):
                self.assertEqual(generate_game(seed).to_dict(), generate_game(seed).to_dict())

    def test_different_seeds_give_different_games(self):
        # Titles are drawn from a large adjective x noun space, so collisions
        # across 40 seeds would mean the RNG is not actually being seeded.
        titles = {generate_game(seed).title for seed in range(1, 41)}
        self.assertGreater(len(titles), 30, "titles are barely varying; is the seed reaching the namer?")

    def test_generation_does_not_touch_global_rng(self):
        # If any generator call reached the module-level `random`, interleaving a
        # generation between two draws would change the second draw.
        import random

        random.seed(12345)
        first = [random.random() for _ in range(5)]
        random.seed(12345)
        generate_game(777)
        second = [random.random() for _ in range(5)]
        self.assertEqual(first, second)

    def test_string_seed_is_coerced(self):
        self.assertEqual(generate_game("42").seed, 42)


class TestValidation(unittest.TestCase):
    def test_every_seed_validates(self):
        for seed in SEEDS:
            with self.subTest(seed=seed):
                validate_game(generate_game(seed))  # raises on failure

    def test_validator_rejects_a_broken_game(self):
        # Guard against the validator silently accepting everything: break a game
        # on purpose and confirm it is caught. Without this, a bug that made
        # validate_game() return early would leave every other test in this class
        # passing vacuously.
        game = generate_game(7)
        self.assertGreater(len(game.resources), 1)
        # Strip every producer except the opening click, orphaning refined tiers.
        orphan = replace(game, generators=(), actions=game.actions[:1])
        with self.assertRaises(InvalidGame):
            validate_game(orphan)

    def test_validator_rejects_a_game_with_no_opener(self):
        game = generate_game(7)
        gated = tuple(
            replace(action, unlock=Unlock("resource_total", game.resources[0].id, 10.0))
            for action in game.actions
        )
        with self.assertRaises(InvalidGame):
            validate_game(replace(game, actions=gated))


class TestStructure(unittest.TestCase):
    def test_run_is_playable_from_the_first_frame(self):
        for seed in SEEDS:
            game = generate_game(seed)
            openers = [a for a in game.actions if a.unlock.kind == "none" and not a.cost]
            self.assertTrue(openers, f"seed {seed} has no free ungated action")

    def test_first_generator_is_reachable(self):
        for seed in SEEDS:
            game = generate_game(seed)
            ungated = [g for g in game.generators if g.unlock.kind == "none"]
            self.assertTrue(ungated, f"seed {seed} gates every generator")

    def test_every_resource_has_a_producer(self):
        for seed in SEEDS:
            game = generate_game(seed)
            produced = {rid for a in game.actions for rid in a.output}
            produced |= {g.resource for g in game.generators}
            for resource in game.resources:
                self.assertIn(resource.id, produced, f"seed {seed}: {resource.id} is unproducible")

    def test_resource_ids_are_unique(self):
        for seed in SEEDS:
            game = generate_game(seed)
            for collection in (game.resources, game.actions, game.generators, game.upgrades):
                ids = [item.id for item in collection]
                self.assertEqual(len(ids), len(set(ids)), f"seed {seed} has duplicate ids: {ids}")

    def test_tier_chain_starts_at_zero_and_has_no_gaps(self):
        for seed in SEEDS:
            game = generate_game(seed)
            tiers = sorted({r.tier for r in game.resources})
            self.assertEqual(tiers[0], 0, f"seed {seed} has no tier-0 resource")
            self.assertEqual(
                tiers, list(range(len(tiers))), f"seed {seed} has a gap in its tier chain: {tiers}"
            )

    def test_upgrade_requirements_are_acyclic(self):
        for seed in SEEDS:
            game = generate_game(seed)
            for upgrade in game.upgrades:
                for required in upgrade.requires:
                    parent = game.upgrade(required)
                    self.assertLess(
                        parent.tier,
                        upgrade.tier,
                        f"seed {seed}: {upgrade.id} requires a same-or-later upgrade",
                    )

    def test_tier_zero_upgrades_are_legible(self):
        # The first upgrade a player buys must have a visible, deterministic
        # effect -- not a probability they cannot feel or verify.
        for seed in SEEDS:
            game = generate_game(seed)
            for upgrade in game.upgrades:
                if upgrade.tier != 0:
                    continue
                kinds = {e.kind for e in upgrade.effects}
                self.assertNotIn("crit_chance", kinds, f"seed {seed}: {upgrade.id} is a tier-0 crit")

    def test_generators_always_have_cost_growth(self):
        # Growth <= 1 would make a generator infinitely buyable at a fixed price.
        for seed in SEEDS:
            for generator in generate_game(seed).generators:
                self.assertGreater(generator.cost_growth, 1.0)

    def test_only_refined_resources_decay(self):
        # A decaying tier-0 resource makes the opening minute feel broken.
        for seed in SEEDS:
            for resource in generate_game(seed).resources:
                if resource.tier == 0:
                    self.assertEqual(resource.decay, 0.0, f"seed {seed}: {resource.id} decays at tier 0")

    def test_mechanic_params_reference_real_content(self):
        for seed in SEEDS:
            game = generate_game(seed)
            resource_ids = {r.id for r in game.resources}
            action_ids = {a.id for a in game.actions}
            for mechanic in game.mechanics:
                params = mechanic.params
                for key in ("resource", "driver", "source", "dest"):
                    if key in params:
                        self.assertIn(params[key], resource_ids, f"{mechanic.id}.{key}")
                for key in ("action", "other_action"):
                    if key in params:
                        self.assertIn(params[key], action_ids, f"{mechanic.id}.{key}")
                if "family" in params:
                    self.assertIn(params["family"], {u.family for u in game.upgrades})

    def test_cascade_never_points_at_itself(self):
        # A self-referential cascade would be a free infinite action.
        for seed in SEEDS:
            for mechanic in generate_game(seed).mechanics_of("cascade"):
                self.assertNotEqual(mechanic.params["action"], mechanic.params["other_action"])

    def test_prestige_is_always_reachable_in_principle(self):
        for seed in SEEDS:
            game = generate_game(seed)
            self.assertGreater(game.prestige_divisor, 0)
            self.assertTrue(game.prestige_upgrades)
            # At least one prestige upgrade must be affordable with the very first
            # point earned, or the meta-loop has no entry.
            cheapest = min(p.base_cost for p in game.prestige_upgrades)
            self.assertLessEqual(cheapest, 2.0, f"seed {seed}: cheapest prestige upgrade costs {cheapest}")


class TestVariety(unittest.TestCase):
    """The whole premise is that runs differ. These tests hold that premise."""

    def test_runs_vary_in_shape(self):
        shapes = {
            (len(g.resources), g.max_tier, len(g.actions), len(g.generators))
            for g in (generate_game(s) for s in range(1, 61))
        }
        self.assertGreater(len(shapes), 20, "generated runs are too structurally similar")

    def test_mechanics_vary(self):
        combos = {
            tuple(sorted(m.kind for m in generate_game(seed).mechanics)) for seed in range(1, 61)
        }
        self.assertGreater(len(combos), 12, "the same mechanics keep being selected")

    def test_every_mechanic_kind_appears_eventually(self):
        seen = {m.kind for seed in range(1, 201) for m in generate_game(seed).mechanics}
        expected = {
            "synergy",
            "cascade",
            "overflow",
            "momentum",
            "resonance",
            "symbiosis",
            "scarcity",
        }
        self.assertEqual(seen, expected, f"never generated: {sorted(expected - seen)}")

    def test_palette_entries_are_distinct(self):
        for seed in range(1, 41):
            game = generate_game(seed)
            colours = [r.color for r in game.resources]
            self.assertEqual(len(colours), len(set(colours)), f"seed {seed} reuses a resource colour")


if __name__ == "__main__":
    unittest.main()
