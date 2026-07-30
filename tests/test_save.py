"""
Save/load round-trips and corruption handling.

A save stores a seed plus progress and regenerates the definition on load, so the
tests that matter are: does progress survive, does offline time get credited, and
does a malformed save fail loudly instead of producing a half-broken run.
"""

from __future__ import annotations

import json
import unittest

from incgame.balance import FakeClock
from incgame.engine import MAX_OFFLINE_SECONDS, GameEngine
from incgame.generator import generate_game
from incgame.save import SAVE_VERSION, SaveError, dump_save, dump_save_text, load_save, load_save_text


def played_engine(seed: int = 42, clock=None):
    """An engine with some genuine progress on it."""
    clock = clock or FakeClock()
    engine = GameEngine(generate_game(seed), clock=clock)
    action = next(a for a in engine.game.actions if not a.cost and engine.is_unlocked(a.unlock))
    for _ in range(30):
        clock.advance(0.2)
        engine.do_action(action.id)
    generator = next(g for g in engine.game.generators if engine.is_unlocked(g.unlock))
    engine.state.amounts[generator.cost_resource] += engine.generator_cost(generator.id) * 3
    engine.buy_generator(generator.id, 2)
    return engine, clock


class TestRoundTrip(unittest.TestCase):
    def test_progress_survives(self):
        engine, clock = played_engine()
        blob = dump_save(engine)

        restored = load_save(blob, clock=clock)
        self.assertEqual(restored.game.seed, engine.game.seed)
        self.assertEqual(restored.state.generators, engine.state.generators)
        self.assertEqual(restored.state.upgrades, engine.state.upgrades)
        self.assertEqual(restored.state.action_count, engine.state.action_count)
        for resource in engine.game.resources:
            self.assertAlmostEqual(
                restored.state.amounts[resource.id],
                engine.state.amounts[resource.id],
                places=6,
            )

    def test_definition_is_not_stored(self):
        # The whole point of seeding: a save is progress, not content.
        engine, _ = played_engine()
        blob = dump_save(engine)
        text = json.dumps(blob)
        self.assertNotIn(engine.game.title, text)
        self.assertNotIn(engine.game.resources[0].name, text)
        self.assertLess(len(text), 4000, "save is carrying content it should regenerate")

    def test_text_round_trip(self):
        engine, clock = played_engine()
        restored = load_save_text(dump_save_text(engine), clock=clock)
        self.assertEqual(restored.game.seed, engine.game.seed)

    def test_prestige_state_survives(self):
        engine, clock = played_engine()
        engine.state.earned[engine.game.resources[0].id] = engine.game.prestige_divisor * 400
        engine.prestige()
        cheapest = min(engine.game.prestige_upgrades, key=lambda p: p.base_cost)
        engine.buy_prestige_upgrade(cheapest.id)

        restored = load_save(dump_save(engine), clock=clock)
        self.assertEqual(restored.state.ascensions, engine.state.ascensions)
        self.assertEqual(restored.state.prestige_levels, engine.state.prestige_levels)
        self.assertAlmostEqual(restored.state.prestige_currency, engine.state.prestige_currency)
        # And the modifiers those levels grant must be live again.
        self.assertAlmostEqual(restored.mods.global_mult, engine.mods.global_mult, places=9)


class TestOfflineOnLoad(unittest.TestCase):
    def test_time_away_is_credited(self):
        engine, clock = played_engine()
        generator = next(g for g in engine.game.generators if engine.state.generators.get(g.id))
        produced = generator.resource
        blob = dump_save(engine)
        before = engine.state.amounts[produced]

        clock.advance(1800.0)
        restored = load_save(blob, clock=clock)
        restored.advance()
        self.assertGreater(restored.state.amounts[produced], before)

    def test_time_away_is_capped(self):
        engine, clock = played_engine()
        blob = dump_save(engine)
        clock.advance(MAX_OFFLINE_SECONDS * 10)
        restored = load_save(blob, clock=clock)
        self.assertAlmostEqual(restored.advance(), MAX_OFFLINE_SECONDS, places=3)

    def test_cooldowns_are_not_restored(self):
        # Returning to a game to find yesterday's cooldowns still ticking is pure
        # annoyance, so action_ready is deliberately not persisted.
        engine, clock = played_engine()
        convert = next((a for a in engine.game.actions if a.cooldown > 0), None)
        if convert is None:
            self.skipTest("this seed has no cooldowns")
        engine.state.action_ready[convert.id] = clock.now + 9999
        restored = load_save(dump_save(engine), clock=clock)
        self.assertEqual(restored.state.action_ready, {})


class TestCorruption(unittest.TestCase):
    def test_missing_seed_is_rejected(self):
        with self.assertRaises(SaveError):
            load_save({"save_version": SAVE_VERSION, "progress": {}})

    def test_wrong_version_is_rejected(self):
        with self.assertRaises(SaveError):
            load_save({"save_version": SAVE_VERSION + 99, "seed": 1})

    def test_non_object_is_rejected(self):
        for junk in ([], "nope", 7, None):
            with self.assertRaises(SaveError):
                load_save(junk)

    def test_invalid_json_is_rejected(self):
        with self.assertRaises(SaveError):
            load_save_text("{not json")

    def test_non_integer_seed_is_rejected(self):
        with self.assertRaises(SaveError):
            load_save({"save_version": SAVE_VERSION, "seed": "banana"})

    def test_generator_version_mismatch_is_rejected(self):
        engine, _ = played_engine()
        blob = dump_save(engine)
        blob["generator_version"] = 999
        with self.assertRaises(SaveError):
            load_save(blob)

    def test_nan_and_infinity_are_sanitised(self):
        # A corrupted amount of inf or NaN would make every affordability
        # comparison behave unpredictably rather than simply failing.
        engine, _ = played_engine()
        blob = dump_save(engine)
        rid = engine.game.resources[0].id
        blob["progress"]["amounts"] = {rid: float("inf")}
        blob["progress"]["prestige_currency"] = float("nan")
        restored = load_save(blob)
        self.assertEqual(restored.state.amounts[rid], 0.0)
        self.assertEqual(restored.state.prestige_currency, 0.0)

    def test_negative_amounts_are_clamped(self):
        engine, _ = played_engine()
        blob = dump_save(engine)
        rid = engine.game.resources[0].id
        blob["progress"]["amounts"] = {rid: -500.0}
        self.assertEqual(load_save(blob).state.amounts[rid], 0.0)

    def test_unknown_ids_are_ignored_not_fatal(self):
        # A save from a build with different generated content should degrade to
        # "you lost some upgrades", never to a crash.
        engine, _ = played_engine()
        blob = dump_save(engine)
        blob["progress"]["upgrades"] = ["ghost_upgrade_from_another_build"]
        blob["progress"]["generators"] = {"ghost_generator": 5}
        blob["progress"]["amounts"]["ghost_resource"] = 100.0
        restored = load_save(blob)
        self.assertEqual(restored.mods.global_mult, 1.0)
        self.assertNotIn("ghost_resource", restored.state.amounts)
        restored.advance()  # must not raise

    def test_missing_progress_block_yields_a_fresh_run(self):
        game = generate_game(11)
        restored = load_save({"save_version": SAVE_VERSION, "seed": 11})
        self.assertEqual(restored.game.seed, game.seed)
        self.assertEqual(restored.state.ascensions, 0)


if __name__ == "__main__":
    unittest.main()
