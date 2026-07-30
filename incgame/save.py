"""
Save format.

A save stores the seed plus player progress -- never the generated definition.
The definition is regenerated from the seed on load, which has three consequences
worth stating outright:

* Saves are tiny and diff-readable.
* A save can never disagree with the generator, because there is only one copy of
  the content and it is derived.
* Changing the generator invalidates old saves. `SAVE_VERSION` and
  `generator_version` exist so that a mismatch is detected and reported instead
  of silently producing a run whose upgrade ids no longer resolve.

The engine already tolerates unknown ids (see `_compute_mods`), so a minor
generator change degrades to "you lost some upgrades" rather than a crash. A
major one should bump `GENERATOR_VERSION` in `generator.py` and be rejected here.
"""

from __future__ import annotations

import json
from typing import Any, Dict

from .engine import GameEngine, GameState
from .generator import generate_game

SAVE_VERSION = 1


class SaveError(Exception):
    """A save could not be read, or does not belong to this build."""


def dump_save(engine: GameEngine) -> Dict[str, Any]:
    """Serialise a live engine into a plain dict, ready for `json.dumps`."""
    engine.advance()
    state = engine.state
    return {
        "save_version": SAVE_VERSION,
        "generator_version": engine.game.generator_version,
        "seed": engine.game.seed,
        "saved_at": state.updated_at,
        "progress": {
            "amounts": {k: v for k, v in state.amounts.items() if v},
            "earned": {k: v for k, v in state.earned.items() if v},
            "lifetime": {k: v for k, v in state.lifetime.items() if v},
            "generators": {k: v for k, v in state.generators.items() if v},
            "upgrades": list(state.upgrades),
            "prestige_currency": state.prestige_currency,
            "prestige_levels": {k: v for k, v in state.prestige_levels.items() if v},
            "ascensions": state.ascensions,
            "action_count": state.action_count,
            "started_at": state.started_at,
            "playtime": state.playtime,
            "best_points": state.best_points,
        },
    }


def dump_save_text(engine: GameEngine) -> str:
    return json.dumps(dump_save(engine), separators=(",", ":"))


def load_save(data: Dict[str, Any], clock=None) -> GameEngine:
    """
    Rebuild an engine from a save dict.

    Offline production is credited by `advance()` on the first tick: `updated_at`
    is restored from the save, so the elapsed wall-clock time since saving is
    simulated (capped in the engine at `MAX_OFFLINE_SECONDS`). Cooldowns are
    deliberately *not* restored -- coming back to a game to find your buttons on
    cooldown from yesterday is pure annoyance with no design value.
    """
    if not isinstance(data, dict):
        raise SaveError("save is not an object")

    version = data.get("save_version")
    if version != SAVE_VERSION:
        raise SaveError(f"unsupported save version {version!r} (this build reads {SAVE_VERSION})")

    if "seed" not in data:
        raise SaveError("save has no seed; the run cannot be regenerated")

    try:
        seed = int(data["seed"])
    except (TypeError, ValueError) as exc:
        raise SaveError("save seed is not an integer") from exc

    game = generate_game(seed)
    saved_generator = data.get("generator_version", game.generator_version)
    if saved_generator != game.generator_version:
        raise SaveError(
            f"save was made by generator v{saved_generator}, this build generates "
            f"v{game.generator_version}; the run would not match"
        )

    progress = data.get("progress") or {}
    state = GameState(
        amounts={r.id: 0.0 for r in game.resources},
        earned=_floats(progress.get("earned")),
        lifetime=_floats(progress.get("lifetime")),
        generators=_ints(progress.get("generators")),
        upgrades=[str(u) for u in progress.get("upgrades") or []],
        prestige_currency=_float(progress.get("prestige_currency")),
        prestige_levels=_ints(progress.get("prestige_levels")),
        ascensions=int(_float(progress.get("ascensions"))),
        action_count=int(_float(progress.get("action_count"))),
        started_at=_float(progress.get("started_at")),
        playtime=_float(progress.get("playtime")),
        best_points=_float(progress.get("best_points")),
    )
    state.amounts.update({k: v for k, v in _floats(progress.get("amounts")).items() if k in state.amounts})
    state.updated_at = _float(data.get("saved_at"))

    engine = GameEngine(game, state=state, clock=clock) if clock else GameEngine(game, state=state)
    if not state.updated_at:
        state.updated_at = engine.clock()
    if not state.started_at:
        state.started_at = engine.clock()
    return engine


def load_save_text(text: str, clock=None) -> GameEngine:
    try:
        data = json.loads(text)
    except json.JSONDecodeError as exc:
        raise SaveError(f"save is not valid JSON: {exc}") from exc
    return load_save(data, clock=clock)


def _float(value: Any) -> float:
    try:
        result = float(value)
    except (TypeError, ValueError):
        return 0.0
    # Reject NaN/inf: a corrupted save should not poison the economy with values
    # that make every comparison false.
    if result != result or result in (float("inf"), float("-inf")):
        return 0.0
    return result


def _floats(value: Any) -> Dict[str, float]:
    if not isinstance(value, dict):
        return {}
    return {str(k): max(0.0, _float(v)) for k, v in value.items()}


def _ints(value: Any) -> Dict[str, int]:
    if not isinstance(value, dict):
        return {}
    return {str(k): max(0, int(_float(v))) for k, v in value.items()}
