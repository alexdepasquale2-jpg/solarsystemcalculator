"""
Engine behaviour: production, spending, gates, mechanics, and prestige.

All of these drive a `FakeClock`, so nothing sleeps and a test covering eight
hours of offline production runs in microseconds.
"""

from __future__ import annotations

import unittest

from incgame.balance import FakeClock
from incgame.engine import MAX_OFFLINE_SECONDS, GameEngine
from incgame.generator import generate_game
from incgame.model import Effect, Mechanic


def engine_for(seed: int = 42):
    clock = FakeClock()
    return GameEngine(generate_game(seed), clock=clock), clock


def first_click(engine):
    return next(a for a in engine.game.actions if not a.cost and engine.is_unlocked(a.unlock))


def force_unlock(engine):
    """
    Satisfy every gate in the run, whatever kind it is.

    Tests about cooldowns and requirements should not also be tests about which
    gate kind a seed happened to roll. Setting lifetime earnings covers resource
    gates; owning the tier-0 tree covers count, family, and upgrade gates.
    """
    huge = 1e12
    engine.state.earned = {r.id: huge for r in engine.game.resources}
    engine.state.amounts = {r.id: huge for r in engine.game.resources}
    engine.state.upgrades = [u.id for u in engine.game.upgrades if u.tier == 0]
    object.__setattr__(engine.state, "_upgrade_set", None)
    engine.state.ascensions = 99
    engine._invalidate()


class TestActions(unittest.TestCase):
    def test_click_produces_its_resource(self):
        engine, _ = engine_for()
        action = first_click(engine)
        resource = next(iter(action.output))
        self.assertEqual(engine.state.amounts[resource], 0.0)
        result = engine.do_action(action.id)
        self.assertTrue(result["ok"])
        self.assertGreater(engine.state.amounts[resource], 0.0)

    def test_unaffordable_action_is_refused_and_changes_nothing(self):
        engine, _ = engine_for()
        convert = next(a for a in engine.game.actions if a.cost)
        before = dict(engine.state.amounts)
        result = engine.do_action(convert.id)
        self.assertFalse(result["ok"])
        self.assertEqual(engine.state.amounts, before)

    def test_cooldown_blocks_a_second_use(self):
        engine, clock = engine_for()
        convert = next(a for a in engine.game.actions if a.cost and a.cooldown > 0)
        force_unlock(engine)

        self.assertTrue(engine.do_action(convert.id)["ok"])
        blocked = engine.do_action(convert.id)
        self.assertFalse(blocked["ok"])
        self.assertEqual(blocked["reason"], "cooling down")

        clock.advance(engine.action_cooldown(convert) + 0.01)
        self.assertTrue(engine.do_action(convert.id)["ok"])

    def test_locked_action_is_refused(self):
        engine, _ = engine_for()
        locked = [a for a in engine.game.actions if not engine.is_unlocked(a.unlock)]
        if not locked:
            self.skipTest("this seed gates nothing")
        self.assertEqual(engine.do_action(locked[0].id)["reason"], "locked")

    def test_unknown_action_is_refused_not_raised(self):
        engine, _ = engine_for()
        self.assertFalse(engine.do_action("no_such_action")["ok"])


class TestGenerators(unittest.TestCase):
    def test_cost_grows_geometrically(self):
        engine, _ = engine_for()
        generator = engine.game.generators[0]
        first = engine.generator_cost(generator.id, 1)
        engine.state.generators[generator.id] = 1
        second = engine.generator_cost(generator.id, 1)
        self.assertAlmostEqual(second, first * generator.cost_growth, places=6)

    def test_bulk_cost_matches_the_sum_of_singles(self):
        # The geometric-series shortcut and a naive loop must agree, or "buy max"
        # charges a different price than it displays.
        engine, _ = engine_for()
        generator = engine.game.generators[0]
        bulk = engine.generator_cost(generator.id, 7)
        stepwise = 0.0
        for _ in range(7):
            stepwise += engine.generator_cost(generator.id, 1)
            engine.state.generators[generator.id] = engine.state.generators.get(generator.id, 0) + 1
        self.assertAlmostEqual(bulk, stepwise, places=4)

    def test_max_affordable_is_exactly_affordable(self):
        engine, _ = engine_for()
        generator = engine.game.generators[0]
        engine.state.amounts[generator.cost_resource] = 5000.0
        count = engine.max_affordable(generator.id)
        self.assertGreater(count, 0)
        self.assertLessEqual(engine.generator_cost(generator.id, count), 5000.0 + 1e-6)
        self.assertGreater(engine.generator_cost(generator.id, count + 1), 5000.0)

    def test_buying_produces_passive_income(self):
        engine, clock = engine_for()
        generator = next(g for g in engine.game.generators if engine.is_unlocked(g.unlock))
        engine.state.amounts[generator.cost_resource] = engine.generator_cost(generator.id) * 2
        self.assertTrue(engine.buy_generator(generator.id)["ok"])

        produced = generator.resource
        engine.state.amounts[produced] = 0.0
        clock.advance(60.0)
        engine.advance()
        self.assertGreater(engine.state.amounts[produced], 0.0)

    def test_buy_max_falls_back_to_what_is_affordable(self):
        engine, _ = engine_for()
        generator = next(g for g in engine.game.generators if engine.is_unlocked(g.unlock))
        engine.state.amounts[generator.cost_resource] = engine.generator_cost(generator.id) * 1.5
        result = engine.buy_generator(generator.id, 99)
        self.assertTrue(result["ok"])
        self.assertEqual(result["bought"], 1)


class TestProduction(unittest.TestCase):
    def test_caps_are_respected(self):
        engine, clock = engine_for()
        capped = next((r for r in engine.game.resources if r.cap != float("inf")), None)
        if capped is None:
            self.skipTest("this seed has no capped resource")
        engine.state.amounts[capped.id] = capped.cap * 0.99
        engine._credit(capped.id, capped.cap * 10)
        self.assertLessEqual(engine.state.amounts[capped.id], engine.cap_of(capped.id) + 1e-9)

    def test_overflow_routes_excess(self):
        engine, _ = engine_for()
        game = engine.game
        source = next((r for r in game.resources if r.cap != float("inf")), None)
        dest = next((r for r in game.resources if source and r.id != source.id), None)
        if source is None or dest is None:
            self.skipTest("this seed cannot express overflow")

        # Wire the mechanic explicitly rather than hunting for a seed that has one.
        object.__setattr__(
            game,
            "mechanics",
            game.mechanics
            + (
                Mechanic(
                    id="test_overflow",
                    kind="overflow",
                    name="Test",
                    description="",
                    params={"source": source.id, "dest": dest.id, "ratio": 0.5},
                ),
            ),
        )
        engine.state.amounts[source.id] = engine.cap_of(source.id)
        engine.state.amounts[dest.id] = 0.0
        engine._credit(source.id, 100.0)
        self.assertAlmostEqual(engine.state.amounts[dest.id], 50.0, places=6)

    def test_decay_reduces_holdings(self):
        engine, clock = engine_for()
        resource = next(r for r in engine.game.resources if r.tier > 0)
        object.__setattr__(resource, "decay", 0.1)
        engine.state.amounts[resource.id] = 1000.0
        clock.advance(10.0)
        engine.advance()
        self.assertLess(engine.state.amounts[resource.id], 1000.0)
        self.assertGreater(engine.state.amounts[resource.id], 0.0)

    def test_upkeep_throttles_instead_of_stopping(self):
        engine, _ = engine_for()
        hungry = next((g for g in engine.game.generators if g.upkeep), None)
        if hungry is None:
            self.skipTest("this seed has no upkeep generator")
        engine.state.generators[hungry.id] = 50
        for rid in hungry.upkeep:
            engine.state.amounts[rid] = 0.0

        _, _, efficiency = engine.rates()
        # Starved, not stopped: efficiency is throttled below 1 but the generator
        # still exists and will recover when fed.
        self.assertLess(efficiency[hungry.id], 1.0)

        for rid, per_unit in hungry.upkeep.items():
            engine.state.amounts[rid] = per_unit * 50 * 1000
        _, _, fed = engine.rates()
        self.assertAlmostEqual(fed[hungry.id], 1.0, places=6)

    def test_net_rate_accounts_for_drain(self):
        engine, _ = engine_for()
        hungry = next((g for g in engine.game.generators if g.upkeep), None)
        if hungry is None:
            self.skipTest("this seed has no upkeep generator")
        engine.state.generators[hungry.id] = 10
        for rid, per_unit in hungry.upkeep.items():
            engine.state.amounts[rid] = per_unit * 10 * 10000
        net = engine.net_rates()
        for rid in hungry.upkeep:
            gross, drain, _ = engine.rates()
            self.assertAlmostEqual(
                net[rid],
                gross.get(rid, 0.0) - drain.get(rid, 0.0),
                places=9,
            )

    def test_amounts_never_go_negative(self):
        engine, clock = engine_for()
        for resource in engine.game.resources:
            engine.state.amounts[resource.id] = 1.0
        for generator in engine.game.generators:
            if generator.upkeep:
                engine.state.generators[generator.id] = 500
        clock.advance(600.0)
        engine.advance()
        for resource in engine.game.resources:
            self.assertGreaterEqual(engine.state.amounts[resource.id], 0.0)


class TestOffline(unittest.TestCase):
    def test_offline_progress_is_credited(self):
        engine, clock = engine_for()
        generator = next(g for g in engine.game.generators if engine.is_unlocked(g.unlock))
        engine.state.amounts[generator.cost_resource] = engine.generator_cost(generator.id) * 2
        engine.buy_generator(generator.id)
        engine.state.amounts[generator.resource] = 0.0

        clock.advance(3600.0)
        simulated = engine.advance()
        self.assertAlmostEqual(simulated, 3600.0, places=3)
        self.assertGreater(engine.state.amounts[generator.resource], 0.0)

    def test_offline_progress_is_capped(self):
        engine, clock = engine_for()
        clock.advance(MAX_OFFLINE_SECONDS * 5)
        simulated = engine.advance()
        self.assertAlmostEqual(simulated, MAX_OFFLINE_SECONDS, places=3)

    def test_advancing_backwards_is_a_no_op(self):
        # Clock skew or a save from the future must not rewind the economy.
        engine, clock = engine_for()
        engine.state.amounts[engine.game.resources[0].id] = 500.0
        clock.advance(-100.0)
        self.assertEqual(engine.advance(), 0.0)
        self.assertEqual(engine.state.amounts[engine.game.resources[0].id], 500.0)


class TestModifiers(unittest.TestCase):
    def test_upgrade_multiplier_applies(self):
        engine, _ = engine_for()
        action = first_click(engine)
        resource = next(iter(action.output))
        before = engine.action_yield(action)[resource]

        object.__setattr__(
            engine.game.upgrades[0], "effects", (Effect("action_yield", action.id, 2.0),)
        )
        engine.state.upgrades.append(engine.game.upgrades[0].id)
        engine._invalidate()
        object.__setattr__(engine.state, "_upgrade_set", None)

        self.assertAlmostEqual(engine.action_yield(action)[resource], before * 2.0, places=9)

    def test_wildcard_and_specific_modifiers_stack(self):
        engine, _ = engine_for()
        action = first_click(engine)
        engine.mods.action_yield["*"] = 2.0
        engine.mods.action_yield[action.id] = 3.0
        self.assertAlmostEqual(engine.mods.multiplier(engine.mods.action_yield, action.id), 6.0)

    def test_reductions_are_floored(self):
        # Stacking many cost reductions must never reach zero or go negative.
        engine, _ = engine_for()
        engine.mods.cooldown["*"] = 1e-9
        self.assertGreaterEqual(engine.mods.reduction(engine.mods.cooldown, "anything"), 0.05)

    def test_unknown_effect_kinds_are_ignored(self):
        # A save from a future build must degrade, not crash.
        engine, _ = engine_for()
        object.__setattr__(engine.game.upgrades[0], "effects", (Effect("from_the_future", "x", 5.0),))
        engine.state.upgrades.append(engine.game.upgrades[0].id)
        engine._invalidate()
        self.assertEqual(engine.mods.global_mult, 1.0)


class TestMechanics(unittest.TestCase):
    def test_momentum_builds_and_resets(self):
        engine, clock = engine_for()
        object.__setattr__(
            engine.game,
            "mechanics",
            (
                Mechanic(
                    id="m",
                    kind="momentum",
                    name="M",
                    description="",
                    params={"window": 2.0, "per_click": 0.1, "max_stacks": 5},
                ),
            ),
        )
        action = first_click(engine)

        engine.do_action(action.id)
        clock.advance(0.5)
        second = engine.do_action(action.id)
        self.assertGreater(second["multiplier"], 1.0)

        clock.advance(10.0)  # past the window
        after_pause = engine.do_action(action.id)
        self.assertAlmostEqual(after_pause["multiplier"], 1.0, places=9)

    def test_momentum_is_capped(self):
        engine, clock = engine_for()
        object.__setattr__(
            engine.game,
            "mechanics",
            (
                Mechanic(
                    id="m",
                    kind="momentum",
                    name="M",
                    description="",
                    params={"window": 5.0, "per_click": 0.1, "max_stacks": 3},
                ),
            ),
        )
        action = first_click(engine)
        best = 0.0
        for _ in range(20):
            clock.advance(0.1)
            best = max(best, engine.do_action(action.id)["multiplier"])
        self.assertAlmostEqual(best, 1.3, places=6)

    def test_resonance_fires_on_schedule(self):
        engine, clock = engine_for()
        object.__setattr__(
            engine.game,
            "mechanics",
            (Mechanic(id="r", kind="resonance", name="R", description="", params={"every_n": 3, "mult": 5.0}),),
        )
        action = first_click(engine)
        multipliers = []
        for _ in range(6):
            clock.advance(0.1)
            multipliers.append(engine.do_action(action.id)["multiplier"])
        # Actions 3 and 6 are the payouts.
        self.assertAlmostEqual(multipliers[2], 5.0, places=6)
        self.assertAlmostEqual(multipliers[5], 5.0, places=6)
        self.assertAlmostEqual(multipliers[0], 1.0, places=6)

    def test_symbiosis_scales_with_the_driver(self):
        engine, _ = engine_for()
        target, driver = engine.game.resources[0], engine.game.resources[-1]
        if target.id == driver.id:
            self.skipTest("this seed has one resource")
        object.__setattr__(
            engine.game,
            "mechanics",
            (
                Mechanic(
                    id="s",
                    kind="symbiosis",
                    name="S",
                    description="",
                    params={"resource": target.id, "driver": driver.id, "coeff": 0.5},
                ),
            ),
        )
        engine.state.amounts[driver.id] = 0.0
        self.assertAlmostEqual(engine._symbiosis_factor(target.id), 1.0, places=9)
        engine.state.amounts[driver.id] = 999.0
        self.assertAlmostEqual(engine._symbiosis_factor(target.id), 2.5, places=6)


class TestDeterministicRandomness(unittest.TestCase):
    def test_rolls_are_reproducible_for_a_given_state(self):
        a, _ = engine_for(123)
        b, _ = engine_for(123)
        self.assertEqual([a._roll(i) for i in range(8)], [b._roll(i) for i in range(8)])

    def test_rolls_change_as_the_run_progresses(self):
        engine, _ = engine_for(123)
        first = engine._roll(1)
        engine.state.action_count += 1
        self.assertNotEqual(first, engine._roll(1))

    def test_rolls_are_in_range(self):
        engine, _ = engine_for(5)
        for count in range(200):
            engine.state.action_count = count
            for salt in range(3):
                value = engine._roll(salt)
                self.assertGreaterEqual(value, 0.0)
                self.assertLess(value, 1.0)


class TestPrestige(unittest.TestCase):
    def test_prestige_needs_progress(self):
        engine, _ = engine_for()
        self.assertFalse(engine.can_prestige())
        self.assertFalse(engine.prestige()["ok"])

    def test_prestige_resets_the_run_and_keeps_meta(self):
        engine, clock = engine_for()
        resource = engine.game.resources[0]
        engine.state.earned[resource.id] = engine.game.prestige_divisor * 100
        engine.state.amounts[resource.id] = 500.0
        engine.state.generators[engine.game.generators[0].id] = 5
        engine.state.upgrades.append(engine.game.upgrades[0].id)

        result = engine.prestige()
        self.assertTrue(result["ok"])
        self.assertGreaterEqual(result["points"], 1)
        self.assertEqual(engine.state.amounts[resource.id], 0.0)
        self.assertEqual(engine.state.generators, {})
        self.assertEqual(engine.state.upgrades, [])
        self.assertEqual(engine.state.earned, {})
        self.assertEqual(engine.state.ascensions, 1)
        self.assertGreaterEqual(engine.state.prestige_currency, 1)

    def test_lifetime_totals_survive_prestige(self):
        engine, _ = engine_for()
        action = first_click(engine)
        engine.do_action(action.id)
        lifetime = dict(engine.state.lifetime)
        engine.state.earned[engine.game.resources[0].id] = engine.game.prestige_divisor * 100
        engine.prestige()
        for rid, value in lifetime.items():
            self.assertGreaterEqual(engine.state.lifetime.get(rid, 0.0), value)

    def test_prestige_upgrade_levels_and_costs(self):
        engine, _ = engine_for()
        repeatable = next((p for p in engine.game.prestige_upgrades if p.max_level > 1), None)
        if repeatable is None:
            self.skipTest("this seed has no repeatable prestige upgrade")
        engine.state.prestige_currency = 1e9
        first = engine.buy_prestige_upgrade(repeatable.id)
        self.assertTrue(first["ok"])
        self.assertEqual(first["level"], 1)
        second = engine.buy_prestige_upgrade(repeatable.id)
        self.assertGreaterEqual(second["paid"], first["paid"])

    def test_prestige_upgrade_respects_max_level(self):
        engine, _ = engine_for()
        one_off = next((p for p in engine.game.prestige_upgrades if p.max_level == 1), None)
        if one_off is None:
            self.skipTest("this seed has no one-off prestige upgrade")
        engine.state.prestige_currency = 1e9
        self.assertTrue(engine.buy_prestige_upgrade(one_off.id)["ok"])
        self.assertEqual(engine.buy_prestige_upgrade(one_off.id)["reason"], "maxed")

    def test_start_resource_applies_after_reset(self):
        engine, _ = engine_for()
        head_start = next(
            (
                p
                for p in engine.game.prestige_upgrades
                if any(e.kind == "start_resource" for e in p.effects)
            ),
            None,
        )
        if head_start is None:
            self.skipTest("this seed has no head-start upgrade")
        engine.state.prestige_currency = 1e9
        engine.buy_prestige_upgrade(head_start.id)
        engine.state.earned[engine.game.resources[0].id] = engine.game.prestige_divisor * 100
        engine.prestige()
        effect = next(e for e in head_start.effects if e.kind == "start_resource")
        self.assertAlmostEqual(engine.state.amounts[effect.target], effect.value, places=6)

    def test_run_score_weights_deeper_tiers_higher(self):
        engine, _ = engine_for()
        deep = max(engine.game.resources, key=lambda r: r.tier)
        shallow = next(r for r in engine.game.resources if r.tier == 0)
        if deep.tier == 0:
            self.skipTest("this seed is flat")
        engine.state.earned = {shallow.id: 100.0}
        shallow_score = engine.run_score()
        engine.state.earned = {deep.id: 100.0}
        self.assertGreater(engine.run_score(), shallow_score)


class TestGates(unittest.TestCase):
    def test_gate_progress_is_bounded(self):
        engine, _ = engine_for()
        for item in list(engine.game.actions) + list(engine.game.generators) + list(engine.game.upgrades):
            progress = engine.gate_progress(item.unlock)
            self.assertGreaterEqual(progress, 0.0)
            self.assertLessEqual(progress, 1.0)

    def test_gate_text_is_never_empty_for_a_real_gate(self):
        engine, _ = engine_for()
        for item in list(engine.game.actions) + list(engine.game.generators) + list(engine.game.upgrades):
            if item.unlock.kind != "none":
                self.assertTrue(engine.gate_text(item.unlock), f"{item.id} has an unexplained gate")

    def test_earning_opens_a_resource_gate(self):
        engine, _ = engine_for()
        gated = next(
            (a for a in engine.game.actions if a.unlock.kind == "resource_total"),
            None,
        )
        if gated is None:
            self.skipTest("this seed has no resource-gated action")
        self.assertFalse(engine.is_unlocked(gated.unlock))
        engine.state.earned[gated.unlock.target] = gated.unlock.amount
        self.assertTrue(engine.is_unlocked(gated.unlock))

    def test_upgrade_requires_are_enforced(self):
        engine, _ = engine_for()
        force_unlock(engine)
        # A chained upgrade whose parent is not in the tier-0 set force_unlock owns.
        chained = next(
            (u for u in engine.game.upgrades if u.requires and u.requires[0] not in engine.state.upgrade_set),
            None,
        )
        if chained is None:
            self.skipTest("this seed has no chained upgrades above tier 0")
        self.assertFalse(engine.upgrade_available(chained))
        engine.state.upgrades.extend(chained.requires)
        object.__setattr__(engine.state, "_upgrade_set", None)
        self.assertTrue(engine.upgrade_available(chained))


class TestEffectText(unittest.TestCase):
    def test_every_generated_effect_renders(self):
        for seed in range(1, 41):
            engine, _ = engine_for(seed)
            for upgrade in engine.game.upgrades:
                text = engine.effects_text(upgrade.effects)
                self.assertTrue(text.strip(), f"seed {seed}: {upgrade.id} has no readable effect")
                self.assertNotIn("None", text)
            for prestige in engine.game.prestige_upgrades:
                self.assertTrue(engine.effects_text(prestige.effects).strip())


if __name__ == "__main__":
    unittest.main()
