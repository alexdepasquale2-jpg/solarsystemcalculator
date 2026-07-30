"""
Immutable data model for a generated run.

A `GameDef` is the *definition* of a game: what exists and what the numbers are.
It contains no mutable player progress -- that lives in `engine.GameState`. The
split matters for saves: a save file stores the seed plus progress, and the
definition is regenerated from the seed on load, so saves stay tiny and can
never disagree with the generator.

Every dataclass here is frozen. If you find yourself wanting to mutate a
`Resource` at runtime, the value belongs in `GameState` instead.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any, Dict, Optional, Tuple

# ---------------------------------------------------------------------------
# Number formatting (mirrored in frontend/js/format.js -- keep both in sync)
# ---------------------------------------------------------------------------

_SUFFIXES = ["", "K", "M", "B", "T", "Qa", "Qi", "Sx", "Sp", "Oc", "No", "Dc"]


def fmt_number(value: float, places: int = 2) -> str:
    """
    Format a number the way an incremental game should: short, monotonic, and
    never surprising. Small values keep decimals, large values get a suffix, and
    anything past decillion falls back to scientific notation.
    """
    if value != value:  # NaN
        return "NaN"
    if value in (float("inf"), float("-inf")):
        return "∞" if value > 0 else "-∞"
    sign = "-" if value < 0 else ""
    value = abs(value)
    if value < 1000:
        if value == int(value):
            return f"{sign}{int(value)}"
        if value < 10:
            return f"{sign}{value:.{places}f}"
        return f"{sign}{value:.1f}"
    tier = int(math.floor(math.log10(value) / 3))
    if tier < len(_SUFFIXES):
        scaled = value / (1000.0**tier)
        return f"{sign}{scaled:.{places}f}{_SUFFIXES[tier]}"
    return f"{sign}{value:.2e}"


def fmt_rate(value: float) -> str:
    """Format a per-second rate, with sign so drains read as drains."""
    if abs(value) < 1e-9:
        return "0/s"
    prefix = "+" if value > 0 else "−"
    return f"{prefix}{fmt_number(abs(value))}/s"


# ---------------------------------------------------------------------------
# Gates
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Unlock:
    """
    A visibility/availability gate.

    kind:
      "none"            always available
      "resource_total"  lifetime earned of `target` >= amount
      "resource_now"    current amount of `target` >= amount
      "upgrades_owned"  total upgrades bought this run >= amount
      "family_owned"    upgrades bought from family `target` >= amount
      "upgrade_owned"   upgrade `target` has been bought
      "generators"      total generators owned of `target` >= amount
      "ascensions"      lifetime prestige count >= amount
    """

    kind: str = "none"
    target: str = ""
    amount: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return {"kind": self.kind, "target": self.target, "amount": self.amount}

    @staticmethod
    def from_dict(data: Dict[str, Any]) -> "Unlock":
        return Unlock(data.get("kind", "none"), data.get("target", ""), float(data.get("amount", 0.0)))


NO_GATE = Unlock()


# ---------------------------------------------------------------------------
# Content
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Resource:
    """
    One currency. `tier` is its depth in the conversion chain: tier 0 is what
    bare hands produce, and each tier above is refined from the one below, so
    higher tiers are rarer and their numbers stay smaller.
    """

    id: str
    name: str
    color: str
    description: str
    tier: int
    base_rate: float = 0.0  # free passive production per second, usually 0
    cap: float = float("inf")
    decay: float = 0.0  # fraction lost per second; drives scarcity mechanics

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "color": self.color,
            "description": self.description,
            "tier": self.tier,
            "base_rate": self.base_rate,
            "cap": None if self.cap == float("inf") else self.cap,
            "decay": self.decay,
        }


@dataclass(frozen=True)
class Action:
    """
    A manual, player-driven verb.

    kind "click"   -- free, yields a tier-0 resource, no cooldown
    kind "convert" -- spends `cost`, yields `output`, has a cooldown
    """

    id: str
    name: str
    description: str
    kind: str
    cost: Dict[str, float] = field(default_factory=dict)
    output: Dict[str, float] = field(default_factory=dict)
    cooldown: float = 0.0
    unlock: Unlock = NO_GATE

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "kind": self.kind,
            "cost": dict(self.cost),
            "output": dict(self.output),
            "cooldown": self.cooldown,
            "unlock": self.unlock.to_dict(),
        }


@dataclass(frozen=True)
class Generator:
    """
    A repeatable purchase that produces passively.

    Cost grows geometrically with the number owned, which is the main pacing
    lever in the genre. `upkeep` is consumed per second per unit; when the
    upkeep resource runs dry the generator throttles instead of stopping, which
    is where a lot of the interesting mid-run tension comes from.
    """

    id: str
    name: str
    description: str
    resource: str  # what it produces
    rate: float  # per second, per unit owned
    cost_resource: str
    base_cost: float
    cost_growth: float
    upkeep: Dict[str, float] = field(default_factory=dict)
    unlock: Unlock = NO_GATE

    def cost_at(self, owned: int) -> float:
        return self.base_cost * (self.cost_growth**owned)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "resource": self.resource,
            "rate": self.rate,
            "cost_resource": self.cost_resource,
            "base_cost": self.base_cost,
            "cost_growth": self.cost_growth,
            "upkeep": dict(self.upkeep),
            "unlock": self.unlock.to_dict(),
        }


@dataclass(frozen=True)
class Effect:
    """
    A single modifier contributed by an upgrade.

    kind             target                 value
    ---------------- ---------------------- ---------------------------------
    global_mult      ""                     multiplier on all production
    resource_rate    resource id or "*"     multiplier on that resource's rate
    resource_cap     resource id or "*"     multiplier on cap
    action_yield     action id or "*"       multiplier on action output
    generator_rate   generator id or "*"    multiplier on generator output
    generator_cost   generator id or "*"    multiplier on cost (<1 is good)
    cooldown         action id or "*"       multiplier on cooldown (<1 is good)
    decay            resource id or "*"     multiplier on decay (<1 is good)
    crit_chance      action id or "*"       added crit chance, extra["mult"]
    start_resource   resource id            amount held at the start of a run
                                            (prestige upgrades only)

    Multipliers of the same kind and target stack multiplicatively. Reduction
    effects (cooldown, decay, generator_cost) are floored in the engine so that
    stacking many of them can approach, but never reach, zero.
    """

    kind: str
    target: str = ""
    value: float = 1.0
    extra: Dict[str, float] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {"kind": self.kind, "target": self.target, "value": self.value, "extra": dict(self.extra)}


@dataclass(frozen=True)
class Upgrade:
    """
    A one-off purchase that changes the arithmetic.

    `family` groups upgrades into schools; synergy mechanics multiply things
    based on how many of a family you own, so families are load-bearing rather
    than decorative.
    """

    id: str
    name: str
    description: str
    family: str
    tier: int
    cost: Dict[str, float]
    effects: Tuple[Effect, ...]
    requires: Tuple[str, ...] = ()
    unlock: Unlock = NO_GATE

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "family": self.family,
            "tier": self.tier,
            "cost": dict(self.cost),
            "effects": [e.to_dict() for e in self.effects],
            "requires": list(self.requires),
            "unlock": self.unlock.to_dict(),
        }


@dataclass(frozen=True)
class PrestigeUpgrade:
    """
    A permanent purchase, paid for in prestige currency, that survives resets.

    Repeatable ones are how a long-running save keeps getting stronger without
    the generator needing to invent unbounded content.
    """

    id: str
    name: str
    description: str
    base_cost: float
    effects: Tuple[Effect, ...]
    max_level: int = 1
    cost_growth: float = 1.0

    def cost_at(self, level: int) -> float:
        return self.base_cost * (self.cost_growth**level)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "base_cost": self.base_cost,
            "effects": [e.to_dict() for e in self.effects],
            "max_level": self.max_level,
            "cost_growth": self.cost_growth,
        }


@dataclass(frozen=True)
class Mechanic:
    """
    An emergent system, wired to specific generated content at generation time.

    Mechanics are the reason two runs with the same resource count still play
    differently. Each `kind` is implemented in `engine.py`; `params` holds the
    ids and coefficients it was wired to.

    kinds:
      "synergy"    params: family, per, effect_kind, target
      "cascade"    params: action, chance, other_action, mult
      "overflow"   params: source, dest, ratio
      "momentum"   params: window, per_click, max_stacks
      "resonance"  params: every_n, mult
      "symbiosis"  params: resource, driver, coeff
      "scarcity"   params: resource, decay        (documents a decaying resource)
    """

    id: str
    kind: str
    name: str
    description: str
    params: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "kind": self.kind,
            "name": self.name,
            "description": self.description,
            "params": dict(self.params),
        }


@dataclass(frozen=True)
class GameDef:
    """The complete generated definition of one run."""

    seed: int
    title: str
    flavor: str
    theme: Dict[str, str]
    resources: Tuple[Resource, ...]
    actions: Tuple[Action, ...]
    generators: Tuple[Generator, ...]
    upgrades: Tuple[Upgrade, ...]
    mechanics: Tuple[Mechanic, ...]
    prestige_name: str
    prestige_color: str
    prestige_upgrades: Tuple[PrestigeUpgrade, ...]
    prestige_divisor: float
    # Geometric growth factor on the score one prestige point costs, per ascension.
    # Without it the meta-loop collapses: permanent multipliers compound, score
    # outruns the sqrt in prestige_points, and runs shrink toward zero.
    prestige_escalation: float = 1.3
    generator_version: int = 1

    # -- lookups -----------------------------------------------------------

    def resource(self, rid: str) -> Resource:
        return self._index("_res", self.resources)[rid]

    def action(self, aid: str) -> Action:
        return self._index("_act", self.actions)[aid]

    def generator(self, gid: str) -> Generator:
        return self._index("_gen", self.generators)[gid]

    def upgrade(self, uid: str) -> Upgrade:
        return self._index("_upg", self.upgrades)[uid]

    def prestige_upgrade(self, pid: str) -> PrestigeUpgrade:
        return self._index("_pup", self.prestige_upgrades)[pid]

    def mechanics_of(self, kind: str) -> Tuple[Mechanic, ...]:
        return tuple(m for m in self.mechanics if m.kind == kind)

    def _index(self, attr: str, items: Tuple[Any, ...]) -> Dict[str, Any]:
        # Frozen dataclass, so caches go through object.__setattr__.
        cached: Optional[Dict[str, Any]] = getattr(self, attr, None)
        if cached is None:
            cached = {item.id: item for item in items}
            object.__setattr__(self, attr, cached)
        return cached

    @property
    def base_resources(self) -> Tuple[Resource, ...]:
        return tuple(r for r in self.resources if r.tier == 0)

    @property
    def max_tier(self) -> int:
        return max((r.tier for r in self.resources), default=0)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "seed": self.seed,
            "title": self.title,
            "flavor": self.flavor,
            "theme": dict(self.theme),
            "generator_version": self.generator_version,
            "resources": [r.to_dict() for r in self.resources],
            "actions": [a.to_dict() for a in self.actions],
            "generators": [g.to_dict() for g in self.generators],
            "upgrades": [u.to_dict() for u in self.upgrades],
            "mechanics": [m.to_dict() for m in self.mechanics],
            "prestige": {
                "name": self.prestige_name,
                "color": self.prestige_color,
                "divisor": self.prestige_divisor,
                "escalation": self.prestige_escalation,
                "upgrades": [p.to_dict() for p in self.prestige_upgrades],
            },
        }
