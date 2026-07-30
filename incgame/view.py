"""
Serialisation of engine state into the payload the frontend renders.

Kept out of `engine.py` on purpose: the engine owns simulation truth, this module
owns what the player is allowed to see. The split is what makes progressive
discovery a presentation concern rather than something threaded through the
economy.

The reveal rule is the interesting part. Content is shown when it is available,
*teased* when the player is part-way to its gate, and hidden otherwise. Seeing a
locked thing you are 60% toward is a goal; having it pop into existence fully
formed is a non-event. `TEASE_THRESHOLD` is that dial.
"""

from __future__ import annotations

from typing import Any, Dict, List

from .engine import GameEngine
from .model import fmt_number

# Fraction of a gate that must be complete before locked content is revealed.
TEASE_THRESHOLD = 0.35
# If nothing at all would be visible in a panel, reveal this many anyway, so no
# panel is ever empty and the player is never left without a next objective.
MIN_VISIBLE = 3


def state_payload(engine: GameEngine, include_def: bool = False) -> Dict[str, Any]:
    """
    Build the full client payload.

    `include_def` adds the static definition (names, colours, flavour). The client
    asks for it once on load and omits it from the ~4Hz polling payload, which
    keeps the steady-state message small enough to be irrelevant on mobile data.
    """
    engine.advance()
    payload: Dict[str, Any] = {
        "seed": engine.game.seed,
        "title": engine.game.title,
        "flavor": engine.game.flavor,
        "theme": dict(engine.game.theme),
        "resources": _resources(engine),
        "actions": _actions(engine),
        "generators": _generators(engine),
        "upgrades": _upgrades(engine),
        "mechanics": _mechanics(engine),
        "prestige": _prestige(engine),
        "stats": _stats(engine),
    }
    if include_def:
        payload["definition"] = engine.game.to_dict()
    return payload


# ---------------------------------------------------------------------------


def _resources(engine: GameEngine) -> List[Dict[str, Any]]:
    net = engine.net_rates()
    gross, drain, _ = engine.rates()
    out: List[Dict[str, Any]] = []
    for resource in engine.game.resources:
        amount = engine.state.amounts.get(resource.id, 0.0)
        cap = engine.cap_of(resource.id)
        earned = engine.state.earned.get(resource.id, 0.0)
        # A resource is worth showing once the player has touched it, or once
        # anything can produce it. Before that it is a spoiler.
        visible = earned > 0 or amount > 0 or resource.tier == 0
        out.append(
            {
                "id": resource.id,
                "name": resource.name,
                "color": resource.color,
                "description": resource.description,
                "tier": resource.tier,
                "amount": amount,
                "display": fmt_number(amount),
                "rate": net.get(resource.id, 0.0),
                "gross": gross.get(resource.id, 0.0),
                "drain": drain.get(resource.id, 0.0),
                "cap": None if cap == float("inf") else cap,
                "cap_display": None if cap == float("inf") else fmt_number(cap),
                "fill": 0.0 if cap == float("inf") else min(1.0, amount / cap if cap else 0.0),
                "decay": engine.decay_of(resource.id),
                "earned": earned,
                "visible": visible,
            }
        )
    return out


def _actions(engine: GameEngine) -> List[Dict[str, Any]]:
    now = engine.clock()
    out: List[Dict[str, Any]] = []
    for action in engine.game.actions:
        progress = engine.gate_progress(action.unlock)
        unlocked = progress >= 1.0
        if not unlocked and progress < TEASE_THRESHOLD:
            continue
        ready_at = engine.state.action_ready.get(action.id, 0.0)
        yields = engine.action_yield(action)
        out.append(
            {
                "id": action.id,
                "name": action.name,
                "description": action.description,
                "kind": action.kind,
                "cost": _bundle(engine, action.cost),
                "output": _bundle(engine, yields),
                "cooldown": engine.action_cooldown(action),
                "ready_in": max(0.0, ready_at - now),
                "affordable": engine.can_afford(action.cost),
                "unlocked": unlocked,
                "progress": progress,
                "gate": engine.gate_text(action.unlock),
            }
        )
    return out


def _generators(engine: GameEngine) -> List[Dict[str, Any]]:
    _, _, efficiency = engine.rates()
    out: List[Dict[str, Any]] = []
    for generator in engine.game.generators:
        progress = engine.gate_progress(generator.unlock)
        unlocked = progress >= 1.0
        owned = engine.state.generators.get(generator.id, 0)
        if not unlocked and progress < TEASE_THRESHOLD and owned == 0:
            continue
        cost = engine.generator_cost(generator.id, 1)
        each = generator.rate * engine.mods.multiplier(engine.mods.generator_rate, generator.id)
        eff = efficiency.get(generator.id, 1.0)
        out.append(
            {
                "id": generator.id,
                "name": generator.name,
                "description": generator.description,
                "resource": generator.resource,
                "resource_name": engine.game.resource(generator.resource).name,
                "owned": owned,
                "rate_each": each,
                "rate_total": each * owned * eff,
                "efficiency": eff,
                "throttled": owned > 0 and eff < 0.999,
                "cost": cost,
                "cost_display": fmt_number(cost),
                "cost_resource": generator.cost_resource,
                "cost_resource_name": engine.game.resource(generator.cost_resource).name,
                "affordable": engine.state.amounts.get(generator.cost_resource, 0.0) >= cost,
                "max_affordable": engine.max_affordable(generator.id),
                "upkeep": _bundle(engine, generator.upkeep),
                "unlocked": unlocked,
                "progress": progress,
                "gate": engine.gate_text(generator.unlock),
            }
        )
    return out


def _upgrades(engine: GameEngine) -> List[Dict[str, Any]]:
    """
    Visible upgrades, cheapest-relevant first.

    Owned upgrades are reported too (the client shows them dimmed) because a tree
    you can no longer see is a tree you cannot reason about.
    """
    owned = engine.state.upgrade_set
    candidates: List[Dict[str, Any]] = []
    hidden: List[Dict[str, Any]] = []

    for upgrade in engine.game.upgrades:
        requirements_met = all(req in owned for req in upgrade.requires)
        progress = engine.gate_progress(upgrade.unlock)
        is_owned = upgrade.id in owned
        entry = {
            "id": upgrade.id,
            "name": upgrade.name,
            "description": upgrade.description,
            "family": upgrade.family,
            "tier": upgrade.tier,
            "cost": _bundle(engine, upgrade.cost),
            "effect": engine.effects_text(upgrade.effects),
            "owned": is_owned,
            "available": (not is_owned) and requirements_met and progress >= 1.0 and engine.can_afford(upgrade.cost),
            "unlocked": requirements_met and progress >= 1.0,
            "progress": progress,
            "gate": engine.gate_text(upgrade.unlock),
            "requires": [
                {"id": req, "name": _upgrade_name(engine, req), "owned": req in owned}
                for req in upgrade.requires
            ],
            "sort": _cost_scale(upgrade.cost),
        }
        if is_owned or (requirements_met and progress >= TEASE_THRESHOLD):
            candidates.append(entry)
        elif not is_owned:
            hidden.append(entry)

    # Never leave the panel empty: surface the nearest few locked upgrades.
    if not any(not e["owned"] for e in candidates) and hidden:
        hidden.sort(key=lambda e: (-e["progress"], e["sort"]))
        candidates.extend(hidden[:MIN_VISIBLE])

    candidates.sort(key=lambda e: (e["owned"], e["tier"], e["sort"]))
    for entry in candidates:
        entry.pop("sort", None)
    return candidates


def _mechanics(engine: GameEngine) -> List[Dict[str, Any]]:
    """
    The run's emergent systems, with live readouts where they have one.

    Mechanics are surfaced explicitly rather than left to be discovered. In a
    generated game the player cannot bring genre knowledge to bear -- they have no
    idea a momentum system exists until told -- and a hidden rule is
    indistinguishable from a bug.
    """
    out: List[Dict[str, Any]] = []
    for mechanic in engine.game.mechanics:
        entry: Dict[str, Any] = {
            "id": mechanic.id,
            "kind": mechanic.kind,
            "name": mechanic.name,
            "description": mechanic.description,
            "live": None,
        }
        if mechanic.kind == "momentum":
            stacks = min(max(0, engine.state.streak - 1), int(mechanic.params["max_stacks"]))
            bonus = 1.0 + float(mechanic.params["per_click"]) * stacks
            entry["live"] = f"{stacks} stacks · ×{bonus:.2f}"
        elif mechanic.kind == "resonance":
            every = int(mechanic.params["every_n"])
            until = every - (engine.state.action_count % every) if every else 0
            entry["live"] = f"{until} action{'s' if until != 1 else ''} to payout"
        elif mechanic.kind == "synergy":
            family = mechanic.params["family"]
            count = sum(1 for uid in engine.state.upgrades if engine.game.upgrade(uid).family == family)
            entry["live"] = f"{count} {family} owned · ×{1 + float(mechanic.params['per']) * count:.2f}"
        elif mechanic.kind == "symbiosis":
            factor = engine._symbiosis_factor(mechanic.params["resource"])
            entry["live"] = f"×{factor:.2f} currently"
        out.append(entry)
    return out


def _prestige(engine: GameEngine) -> Dict[str, Any]:
    points = engine.prestige_points()
    upgrades: List[Dict[str, Any]] = []
    for prestige in engine.game.prestige_upgrades:
        level = engine.state.prestige_levels.get(prestige.id, 0)
        maxed = level >= prestige.max_level
        cost = prestige.cost_at(level)
        upgrades.append(
            {
                "id": prestige.id,
                "name": prestige.name,
                "description": prestige.description,
                "effect": engine.effects_text(prestige.effects),
                "level": level,
                "max_level": prestige.max_level,
                "maxed": maxed,
                "cost": cost,
                "cost_display": fmt_number(cost),
                "affordable": (not maxed) and engine.state.prestige_currency >= cost,
            }
        )
    return {
        "name": engine.game.prestige_name,
        "color": engine.game.prestige_color,
        "currency": engine.state.prestige_currency,
        "currency_display": fmt_number(engine.state.prestige_currency),
        "points": points,
        "points_display": fmt_number(points),
        "can_prestige": points >= 1.0,
        "run_score": engine.run_score(),
        "ascensions": engine.state.ascensions,
        "upgrades": upgrades,
    }


def _stats(engine: GameEngine) -> Dict[str, Any]:
    state = engine.state
    return {
        "playtime": state.playtime,
        "playtime_display": _duration(state.playtime),
        "actions": state.action_count,
        "upgrades_owned": len(state.upgrades),
        "generators_owned": sum(state.generators.values()),
        "ascensions": state.ascensions,
        "best_points": state.best_points,
        "streak": state.streak,
    }


# ---------------------------------------------------------------------------


def _bundle(engine: GameEngine, bundle: Dict[str, float]) -> List[Dict[str, Any]]:
    """Turn a {resource_id: amount} map into something renderable."""
    out: List[Dict[str, Any]] = []
    for resource_id, amount in bundle.items():
        try:
            resource = engine.game.resource(resource_id)
        except KeyError:
            continue
        out.append(
            {
                "id": resource_id,
                "name": resource.name,
                "color": resource.color,
                "amount": amount,
                "display": fmt_number(amount),
                "have": engine.state.amounts.get(resource_id, 0.0) >= amount,
            }
        )
    return out


def _cost_scale(cost: Dict[str, float]) -> float:
    return sum(cost.values()) if cost else 0.0


def _upgrade_name(engine: GameEngine, upgrade_id: str) -> str:
    try:
        return engine.game.upgrade(upgrade_id).name
    except KeyError:
        return upgrade_id


def _duration(seconds: float) -> str:
    seconds = int(max(0.0, seconds))
    hours, remainder = divmod(seconds, 3600)
    minutes, secs = divmod(remainder, 60)
    if hours:
        return f"{hours}h {minutes}m"
    if minutes:
        return f"{minutes}m {secs}s"
    return f"{secs}s"
