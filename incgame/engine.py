"""
Runtime: mutable player progress and the simulation that moves it forward.

Two design rules hold this file together.

**The clock is injected.** `GameEngine` takes a `clock` callable, so the same code
path runs the live game, the offline catch-up on load, and the headless balance
harness at thousands of times real speed. Nothing here calls `time.time()`
directly except the default clock.

**Randomness is derived from the save.** Crits and cascades roll from an RNG
seeded on (run seed, action counter), both of which are saved. A given save file
therefore replays identically -- reproducibility survives the random parts.
"""

from __future__ import annotations

import math
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Set, Tuple

from .model import Action, Effect, GameDef, Generator, Unlock, Upgrade, fmt_number

# A single simulation step never covers more than this many seconds while the
# player is present, so cooldowns and cap overflow land on sane boundaries.
LIVE_STEP = 0.5
# Offline catch-up uses coarser steps; nothing sub-minute matters after an hour.
IDLE_STEP = 5.0
# Generosity limit on offline progress.
MAX_OFFLINE_SECONDS = 8 * 3600.0
# Reduction effects are floored so stacking cannot reach zero or go negative.
MIN_REDUCTION = 0.05


# ---------------------------------------------------------------------------
# Modifier stack
# ---------------------------------------------------------------------------


@dataclass
class Modifiers:
    """
    The flattened result of every owned upgrade, prestige level, and synergy.

    Recomputed from scratch whenever a purchase happens rather than adjusted
    incrementally: the whole stack is a pure function of what you own, so there
    is no drift to debug, and rebuilding it costs microseconds.
    """

    global_mult: float = 1.0
    resource_rate: Dict[str, float] = field(default_factory=dict)
    resource_cap: Dict[str, float] = field(default_factory=dict)
    action_yield: Dict[str, float] = field(default_factory=dict)
    generator_rate: Dict[str, float] = field(default_factory=dict)
    generator_cost: Dict[str, float] = field(default_factory=dict)
    cooldown: Dict[str, float] = field(default_factory=dict)
    decay: Dict[str, float] = field(default_factory=dict)
    crit_chance: Dict[str, float] = field(default_factory=dict)
    crit_mult: Dict[str, float] = field(default_factory=dict)
    start_resource: Dict[str, float] = field(default_factory=dict)

    def multiplier(self, table: Dict[str, float], key: str) -> float:
        """Specific-target and wildcard modifiers multiply together."""
        return table.get(key, 1.0) * table.get("*", 1.0)

    def reduction(self, table: Dict[str, float], key: str) -> float:
        return max(MIN_REDUCTION, self.multiplier(table, key))


# ---------------------------------------------------------------------------
# Player state
# ---------------------------------------------------------------------------


@dataclass
class GameState:
    """Everything about a run that a save file has to remember."""

    amounts: Dict[str, float] = field(default_factory=dict)
    earned: Dict[str, float] = field(default_factory=dict)  # this run, for prestige
    lifetime: Dict[str, float] = field(default_factory=dict)  # all runs, for stats
    generators: Dict[str, int] = field(default_factory=dict)
    upgrades: List[str] = field(default_factory=list)
    prestige_currency: float = 0.0
    prestige_levels: Dict[str, int] = field(default_factory=dict)
    ascensions: int = 0
    action_ready: Dict[str, float] = field(default_factory=dict)
    action_count: int = 0  # drives resonance and the RNG stream
    streak: int = 0
    last_action_at: float = 0.0
    started_at: float = 0.0
    updated_at: float = 0.0
    playtime: float = 0.0
    best_points: float = 0.0

    # Not saved: transient UI notifications.
    log: List[Dict[str, Any]] = field(default_factory=list)

    @property
    def upgrade_set(self) -> Set[str]:
        cached = getattr(self, "_upgrade_set", None)
        if cached is None or len(cached) != len(self.upgrades):
            cached = set(self.upgrades)
            object.__setattr__(self, "_upgrade_set", cached)
        return cached


# ---------------------------------------------------------------------------
# Engine
# ---------------------------------------------------------------------------


class GameEngine:
    """
    Drives one run.

    All public mutators call `advance()` first, so production is always credited
    up to the instant of the action. That means a player who clicks after idling
    gets the idle production too, and the balance harness gets the same behaviour
    without special-casing.
    """

    def __init__(
        self,
        game: GameDef,
        state: Optional[GameState] = None,
        clock: Callable[[], float] = time.time,
    ):
        self.game = game
        self.clock = clock
        self.state = state or GameState()
        self._mods: Optional[Modifiers] = None

        now = self.clock()
        if not self.state.amounts:
            self._reset_run(now)
        if not self.state.started_at:
            self.state.started_at = now
        if not self.state.updated_at:
            self.state.updated_at = now

    # -- modifiers ---------------------------------------------------------

    @property
    def mods(self) -> Modifiers:
        if self._mods is None:
            self._mods = self._compute_mods()
        return self._mods

    def _invalidate(self) -> None:
        self._mods = None

    def _compute_mods(self) -> Modifiers:
        mods = Modifiers()

        for upgrade_id in self.state.upgrades:
            try:
                upgrade = self.game.upgrade(upgrade_id)
            except KeyError:
                continue  # save from an older generator version; ignore politely
            for effect in upgrade.effects:
                self._apply_effect(mods, effect, 1)

        for prestige_id, level in self.state.prestige_levels.items():
            if level <= 0:
                continue
            try:
                prestige = self.game.prestige_upgrade(prestige_id)
            except KeyError:
                continue
            for effect in prestige.effects:
                self._apply_effect(mods, effect, level)

        self._apply_synergies(mods)
        return mods

    def _apply_effect(self, mods: Modifiers, effect: Effect, level: int) -> None:
        """Fold one effect into the stack, applied `level` times."""
        kind, target, value = effect.kind, effect.target or "*", effect.value

        if kind == "global_mult":
            mods.global_mult *= value**level
        elif kind == "resource_rate":
            _mul(mods.resource_rate, target, value**level)
        elif kind == "resource_cap":
            _mul(mods.resource_cap, target, value**level)
        elif kind == "action_yield":
            _mul(mods.action_yield, target, value**level)
        elif kind == "generator_rate":
            _mul(mods.generator_rate, target, value**level)
        elif kind == "generator_cost":
            _mul(mods.generator_cost, target, value**level)
        elif kind == "cooldown":
            _mul(mods.cooldown, target, value**level)
        elif kind == "decay":
            _mul(mods.decay, target, value**level)
        elif kind == "crit_chance":
            # Chances add; the payout multiplier takes the best available.
            mods.crit_chance[target] = mods.crit_chance.get(target, 0.0) + value * level
            best = float(effect.extra.get("mult", 2.0))
            mods.crit_mult[target] = max(mods.crit_mult.get(target, 1.0), best)
        elif kind == "start_resource":
            mods.start_resource[target] = mods.start_resource.get(target, 0.0) + value * level
        # Unknown kinds are ignored rather than fatal: a save may predate them.

    def _apply_synergies(self, mods: Modifiers) -> None:
        """
        Apply the run's synergy mechanics on top of the flat stack.

        Synergies read the *count* of what you own, so they have to run after the
        upgrade loop -- this is the step that makes "ten cheap upgrades from one
        family" a viable strategy against "three expensive ones".
        """
        for mechanic in self.game.mechanics_of("synergy"):
            family = mechanic.params["family"]
            per = float(mechanic.params["per"])
            owned = sum(1 for uid in self.state.upgrades if self._family_of(uid) == family)
            if owned <= 0:
                continue
            factor = 1.0 + per * owned
            kind = mechanic.params.get("effect_kind", "global_mult")
            if kind == "global_mult":
                mods.global_mult *= factor
            elif kind == "action_yield":
                _mul(mods.action_yield, "*", factor)
            elif kind == "generator_rate":
                _mul(mods.generator_rate, "*", factor)

    def _family_of(self, upgrade_id: str) -> str:
        try:
            return self.game.upgrade(upgrade_id).family
        except KeyError:
            return ""

    # -- derived numbers ---------------------------------------------------

    def cap_of(self, resource_id: str) -> float:
        base = self.game.resource(resource_id).cap
        if base == float("inf"):
            return float("inf")
        return base * self.mods.multiplier(self.mods.resource_cap, resource_id)

    def decay_of(self, resource_id: str) -> float:
        base = self.game.resource(resource_id).decay
        if base <= 0:
            return 0.0
        return base * self.mods.reduction(self.mods.decay, resource_id)

    def generator_cost(self, generator_id: str, count: int = 1) -> float:
        """
        Cost of buying `count` more of a generator.

        Geometric series rather than a loop, so "buy 500" is one expression and
        cannot drift from what the purchase actually charges.
        """
        generator = self.game.generator(generator_id)
        owned = self.state.generators.get(generator_id, 0)
        growth = generator.cost_growth
        discount = self.mods.reduction(self.mods.generator_cost, generator_id)
        first = generator.base_cost * (growth**owned) * discount
        if count <= 1:
            return first
        return first * (growth**count - 1.0) / (growth - 1.0)

    def max_affordable(self, generator_id: str, limit: int = 1000) -> int:
        """How many of a generator the player could buy right now."""
        generator = self.game.generator(generator_id)
        available = self.state.amounts.get(generator.cost_resource, 0.0)
        first = self.generator_cost(generator_id, 1)
        if available < first:
            return 0
        growth = generator.cost_growth
        # Invert the geometric series: available >= first * (g^n - 1)/(g - 1)
        ratio = available * (growth - 1.0) / first + 1.0
        count = int(math.floor(math.log(ratio) / math.log(growth)))
        return max(0, min(limit, count))

    def action_yield(self, action: Action) -> Dict[str, float]:
        """Output of one use of an action, with every static multiplier applied."""
        multiplier = (
            self.mods.multiplier(self.mods.action_yield, action.id) * self.mods.global_mult
        )
        return {rid: amount * multiplier for rid, amount in action.output.items()}

    def action_cooldown(self, action: Action) -> float:
        if action.cooldown <= 0:
            return 0.0
        return action.cooldown * self.mods.reduction(self.mods.cooldown, action.id)

    def rates(self) -> Tuple[Dict[str, float], Dict[str, float], Dict[str, float]]:
        """
        Compute current production, drain, and per-generator efficiency.

        Returns (gross, drain, efficiency). A generator whose upkeep resource is
        running dry does not stop -- it throttles proportionally. That single
        choice is responsible for most of the mid-run tension in a generated
        economy: overbuilding a tier-2 farm quietly starves the tier-1 stock that
        feeds it, and the fix is a decision, not a reload.
        """
        state, mods = self.state, self.mods
        gross: Dict[str, float] = {}
        drain: Dict[str, float] = {}
        efficiency: Dict[str, float] = {}

        # First pass: what each generator wants to consume.
        demand: Dict[str, float] = {}
        for generator in self.game.generators:
            owned = state.generators.get(generator.id, 0)
            if owned <= 0:
                continue
            for rid, per_unit in generator.upkeep.items():
                demand[rid] = demand.get(rid, 0.0) + per_unit * owned

        # Second pass: throttle to what is actually on hand plus what is flowing in.
        supply_ratio: Dict[str, float] = {}
        for rid, wanted in demand.items():
            if wanted <= 0:
                continue
            on_hand = state.amounts.get(rid, 0.0)
            # A resource with stock is fine; a resource at zero can only support
            # upkeep from its own incoming production this instant.
            incoming = self._raw_production(rid)
            capacity = on_hand + incoming
            supply_ratio[rid] = 1.0 if capacity >= wanted else max(0.0, capacity / wanted)

        for generator in self.game.generators:
            owned = state.generators.get(generator.id, 0)
            if owned <= 0:
                continue
            eff = 1.0
            for rid in generator.upkeep:
                eff = min(eff, supply_ratio.get(rid, 1.0))
            efficiency[generator.id] = eff
            if eff <= 0:
                continue
            produced = (
                generator.rate
                * owned
                * eff
                * mods.multiplier(mods.generator_rate, generator.id)
            )
            gross[generator.resource] = gross.get(generator.resource, 0.0) + produced
            for rid, per_unit in generator.upkeep.items():
                drain[rid] = drain.get(rid, 0.0) + per_unit * owned * eff

        # Free passive production, resource multipliers, symbiosis, global.
        for resource in self.game.resources:
            total = gross.get(resource.id, 0.0) + resource.base_rate
            if total <= 0:
                gross[resource.id] = 0.0
                continue
            total *= mods.multiplier(mods.resource_rate, resource.id)
            total *= mods.global_mult
            total *= self._symbiosis_factor(resource.id)
            gross[resource.id] = total

        return gross, drain, efficiency

    def _raw_production(self, resource_id: str) -> float:
        """Untuned production of one resource, used only for upkeep throttling."""
        total = self.game.resource(resource_id).base_rate
        for generator in self.game.generators:
            if generator.resource != resource_id:
                continue
            owned = self.state.generators.get(generator.id, 0)
            if owned > 0:
                total += generator.rate * owned
        return total

    def _symbiosis_factor(self, resource_id: str) -> float:
        """Production bonus from holding a partner resource (log-scaled)."""
        factor = 1.0
        for mechanic in self.game.mechanics_of("symbiosis"):
            if mechanic.params["resource"] != resource_id:
                continue
            driver = self.state.amounts.get(mechanic.params["driver"], 0.0)
            coeff = float(mechanic.params["coeff"])
            factor *= 1.0 + coeff * math.log10(1.0 + max(0.0, driver))
        return factor

    def net_rates(self) -> Dict[str, float]:
        """Production minus upkeep minus decay: the number the UI shows."""
        gross, drain, _ = self.rates()
        net: Dict[str, float] = {}
        for resource in self.game.resources:
            value = gross.get(resource.id, 0.0) - drain.get(resource.id, 0.0)
            decay = self.decay_of(resource.id)
            if decay > 0:
                value -= self.state.amounts.get(resource.id, 0.0) * decay
            net[resource.id] = value
        return net

    # -- simulation --------------------------------------------------------

    def advance(self, now: Optional[float] = None) -> float:
        """
        Simulate forward to `now`. Returns the number of seconds simulated.

        Long gaps are chunked rather than applied in one step because decay,
        caps, and overflow are all path-dependent -- a single 4-hour step would
        credit production that a cap should have thrown away.
        """
        now = self.clock() if now is None else now
        elapsed = now - self.state.updated_at
        if elapsed <= 0:
            self.state.updated_at = now
            return 0.0

        simulated = min(elapsed, MAX_OFFLINE_SECONDS)
        remaining = simulated
        while remaining > 1e-9:
            step = min(remaining, IDLE_STEP if remaining > 60.0 else LIVE_STEP)
            self._step(step)
            remaining -= step

        self.state.playtime += simulated
        self.state.updated_at = now
        return simulated

    def _step(self, dt: float) -> None:
        gross, drain, _ = self.rates()
        state = self.state

        for rid, amount in drain.items():
            if amount > 0:
                state.amounts[rid] = max(0.0, state.amounts.get(rid, 0.0) - amount * dt)

        for rid, amount in gross.items():
            if amount > 0:
                self._credit(rid, amount * dt)

        for resource in self.game.resources:
            decay = self.decay_of(resource.id)
            if decay > 0:
                held = state.amounts.get(resource.id, 0.0)
                if held > 0:
                    state.amounts[resource.id] = held * math.exp(-decay * dt)

    def _credit(self, resource_id: str, amount: float) -> None:
        """
        Add resources, respecting the cap and routing the excess.

        This is the only place `amounts` grows, which is what makes lifetime
        earnings (and therefore prestige value) impossible to accidentally
        double-count.
        """
        if amount <= 0:
            return
        state = self.state
        cap = self.cap_of(resource_id)
        current = state.amounts.get(resource_id, 0.0)

        if cap == float("inf") or current + amount <= cap:
            state.amounts[resource_id] = current + amount
            state.earned[resource_id] = state.earned.get(resource_id, 0.0) + amount
            state.lifetime[resource_id] = state.lifetime.get(resource_id, 0.0) + amount
            return

        room = max(0.0, cap - current)
        state.amounts[resource_id] = cap
        if room > 0:
            state.earned[resource_id] = state.earned.get(resource_id, 0.0) + room
            state.lifetime[resource_id] = state.lifetime.get(resource_id, 0.0) + room

        excess = amount - room
        self._spill(resource_id, excess)

    def _spill(self, resource_id: str, excess: float) -> None:
        """Route over-cap production through any overflow mechanic. Never recurses."""
        if excess <= 0:
            return
        for mechanic in self.game.mechanics_of("overflow"):
            if mechanic.params["source"] != resource_id:
                continue
            dest = mechanic.params["dest"]
            gained = excess * float(mechanic.params["ratio"])
            if gained <= 0:
                continue
            cap = self.cap_of(dest)
            current = self.state.amounts.get(dest, 0.0)
            retained = gained if cap == float("inf") else max(0.0, min(gained, cap - current))
            if retained > 0:
                self.state.amounts[dest] = current + retained
                self.state.earned[dest] = self.state.earned.get(dest, 0.0) + retained
                self.state.lifetime[dest] = self.state.lifetime.get(dest, 0.0) + retained

    # -- randomness --------------------------------------------------------

    def _roll(self, salt: int = 0) -> float:
        """
        A deterministic pseudo-random float in [0, 1).

        Derived from the run seed and the action counter, both of which live in
        the save, so replaying a save reproduces every crit and every cascade.
        Uses an integer hash rather than a `random.Random` instance because this
        runs on every click and allocation would show up in the balance harness.
        """
        x = (self.game.seed * 6364136223846793005 + self.state.action_count * 1442695040888963407) & (
            2**64 - 1
        )
        x ^= (salt + 1) * 0x9E3779B97F4A7C15
        x &= 2**64 - 1
        x ^= x >> 33
        x = (x * 0xFF51AFD7ED558CCD) & (2**64 - 1)
        x ^= x >> 33
        return (x % 1_000_000_007) / 1_000_000_007.0

    # -- player actions ----------------------------------------------------

    def do_action(self, action_id: str, now: Optional[float] = None) -> Dict[str, Any]:
        now = self.clock() if now is None else now
        self.advance(now)

        try:
            action = self.game.action(action_id)
        except KeyError:
            return {"ok": False, "reason": "no such action"}

        if not self.is_unlocked(action.unlock):
            return {"ok": False, "reason": "locked"}

        ready_at = self.state.action_ready.get(action_id, 0.0)
        if now < ready_at:
            return {"ok": False, "reason": "cooling down", "ready_in": ready_at - now}

        if not self.can_afford(action.cost):
            return {"ok": False, "reason": "cannot afford"}

        self._spend(action.cost)
        self.state.action_count += 1

        # Momentum before resonance: streak state has to update on every action,
        # whereas resonance only reads the counter.
        multiplier = self._momentum_multiplier(now)
        self.state.last_action_at = now

        multiplier *= self._resonance_multiplier()
        crit = self._crit_multiplier(action)
        multiplier *= crit

        gained = {rid: amount * multiplier for rid, amount in self.action_yield(action).items()}
        for rid, amount in gained.items():
            self._credit(rid, amount)

        cooldown = self.action_cooldown(action)
        if cooldown > 0:
            self.state.action_ready[action_id] = now + cooldown

        result: Dict[str, Any] = {
            "ok": True,
            "action": action_id,
            "gained": gained,
            "multiplier": multiplier,
            "crit": crit > 1.0,
            "streak": self.state.streak,
        }

        cascade = self._maybe_cascade(action, now)
        if cascade:
            result["cascade"] = cascade
        return result

    def _momentum_multiplier(self, now: float) -> float:
        mechanics = self.game.mechanics_of("momentum")
        if not mechanics:
            self.state.streak = 1
            return 1.0
        mechanic = mechanics[0]
        window = float(mechanic.params["window"])
        if self.state.last_action_at and now - self.state.last_action_at <= window:
            self.state.streak += 1
        else:
            self.state.streak = 1
        stacks = min(self.state.streak - 1, int(mechanic.params["max_stacks"]))
        return 1.0 + float(mechanic.params["per_click"]) * stacks

    def _resonance_multiplier(self) -> float:
        for mechanic in self.game.mechanics_of("resonance"):
            every = int(mechanic.params["every_n"])
            if every > 0 and self.state.action_count % every == 0:
                return float(mechanic.params["mult"])
        return 1.0

    def _crit_multiplier(self, action: Action) -> float:
        chance = self.mods.crit_chance.get(action.id, 0.0) + self.mods.crit_chance.get("*", 0.0)
        if chance <= 0:
            return 1.0
        if self._roll(salt=1) < min(0.95, chance):
            return max(
                self.mods.crit_mult.get(action.id, 1.0),
                self.mods.crit_mult.get("*", 1.0),
            )
        return 1.0

    def _maybe_cascade(self, action: Action, now: float) -> Optional[Dict[str, Any]]:
        """
        Fire a chained action for free. Deliberately one level deep -- allowing
        cascades to cascade turns a generated 12% chance into an unbounded loop
        on the seeds where two actions happen to point at each other.
        """
        for mechanic in self.game.mechanics_of("cascade"):
            if mechanic.params["action"] != action.id:
                continue
            if self._roll(salt=2) >= float(mechanic.params["chance"]):
                continue
            try:
                other = self.game.action(mechanic.params["other_action"])
            except KeyError:
                continue
            if not self.is_unlocked(other.unlock):
                continue
            gained = {
                rid: amount * float(mechanic.params.get("mult", 1.0))
                for rid, amount in self.action_yield(other).items()
            }
            for rid, amount in gained.items():
                self._credit(rid, amount)
            return {"action": other.id, "name": other.name, "gained": gained}
        return None

    def buy_generator(self, generator_id: str, count: Any = 1, now: Optional[float] = None) -> Dict[str, Any]:
        """Buy `count` generators, or as many as possible when count == "max"."""
        self.advance(now)
        try:
            generator = self.game.generator(generator_id)
        except KeyError:
            return {"ok": False, "reason": "no such generator"}
        if not self.is_unlocked(generator.unlock):
            return {"ok": False, "reason": "locked"}

        if count == "max":
            wanted = self.max_affordable(generator_id)
        else:
            wanted = max(1, int(count))
        if wanted <= 0:
            return {"ok": False, "reason": "cannot afford"}

        price = self.generator_cost(generator_id, wanted)
        if self.state.amounts.get(generator.cost_resource, 0.0) < price:
            # Requested more than affordable: fall back to the affordable amount.
            wanted = self.max_affordable(generator_id)
            if wanted <= 0:
                return {"ok": False, "reason": "cannot afford"}
            price = self.generator_cost(generator_id, wanted)

        self._spend({generator.cost_resource: price})
        self.state.generators[generator_id] = self.state.generators.get(generator_id, 0) + wanted
        return {"ok": True, "generator": generator_id, "bought": wanted, "paid": price}

    def buy_upgrade(self, upgrade_id: str, now: Optional[float] = None) -> Dict[str, Any]:
        self.advance(now)
        try:
            upgrade = self.game.upgrade(upgrade_id)
        except KeyError:
            return {"ok": False, "reason": "no such upgrade"}
        if upgrade_id in self.state.upgrade_set:
            return {"ok": False, "reason": "already owned"}
        if not self.upgrade_available(upgrade):
            return {"ok": False, "reason": "locked"}
        if not self.can_afford(upgrade.cost):
            return {"ok": False, "reason": "cannot afford"}

        self._spend(upgrade.cost)
        self.state.upgrades.append(upgrade_id)
        object.__setattr__(self.state, "_upgrade_set", None)
        self._invalidate()
        return {"ok": True, "upgrade": upgrade_id, "name": upgrade.name}

    def buy_prestige_upgrade(self, prestige_id: str, now: Optional[float] = None) -> Dict[str, Any]:
        self.advance(now)
        try:
            prestige = self.game.prestige_upgrade(prestige_id)
        except KeyError:
            return {"ok": False, "reason": "no such upgrade"}
        level = self.state.prestige_levels.get(prestige_id, 0)
        if level >= prestige.max_level:
            return {"ok": False, "reason": "maxed"}
        price = prestige.cost_at(level)
        if self.state.prestige_currency < price:
            return {"ok": False, "reason": "cannot afford"}

        self.state.prestige_currency -= price
        self.state.prestige_levels[prestige_id] = level + 1
        self._invalidate()
        return {"ok": True, "upgrade": prestige_id, "level": level + 1, "paid": price}

    # -- prestige ----------------------------------------------------------

    def run_score(self) -> float:
        """
        Value of this run, weighting each resource by how deep it sits in the
        chain. Without the tier weight, prestige would reward grinding the
        cheapest resource forever instead of pushing the economy downstream.
        """
        weight_base = 10.0
        total = 0.0
        for resource in self.game.resources:
            earned = self.state.earned.get(resource.id, 0.0)
            if earned > 0:
                total += earned * (weight_base**resource.tier)
        return total

    def prestige_requirement(self) -> float:
        """
        Score needed per prestige point, escalating with each ascension.

        Geometric, not linear. The square root in `prestige_points` is not enough
        on its own: permanent multipliers compound, so score grows *geometrically*
        across ascensions while sqrt only halves the exponent. Points keep climbing,
        the next reset stays trivially reachable, and the loop collapses toward a
        25-second treadmill -- measured at 84 ascensions in twenty minutes on a deep
        seed. A linear surcharge loses that race for the same reason; only
        exponential growth on the requirement matches exponential growth in output.
        """
        return self.game.prestige_divisor * (
            self.game.prestige_escalation ** self.state.ascensions
        )

    def prestige_points(self) -> float:
        score = self.run_score()
        if score <= 0:
            return 0.0
        return math.floor(math.sqrt(score / self.prestige_requirement()))

    def can_prestige(self) -> bool:
        return self.prestige_points() >= 1.0

    def prestige(self, now: Optional[float] = None) -> Dict[str, Any]:
        now = self.clock() if now is None else now
        self.advance(now)
        points = self.prestige_points()
        if points < 1.0:
            return {"ok": False, "reason": "not enough progress", "points": points}

        self.state.prestige_currency += points
        self.state.best_points = max(self.state.best_points, points)
        self.state.ascensions += 1
        self._reset_run(now)
        return {"ok": True, "points": points, "ascensions": self.state.ascensions}

    def _reset_run(self, now: float) -> None:
        """
        Wipe run progress, keep meta progress, then apply head starts.

        Called on prestige and on first construction, so a brand-new game and a
        post-prestige game go through exactly the same setup path.
        """
        state = self.state
        state.amounts = {r.id: 0.0 for r in self.game.resources}
        state.earned = {}
        state.generators = {}
        state.upgrades = []
        object.__setattr__(state, "_upgrade_set", None)
        state.action_ready = {}
        state.action_count = 0
        state.streak = 0
        state.last_action_at = 0.0
        state.updated_at = now
        self._invalidate()

        for resource_id, amount in self.mods.start_resource.items():
            if resource_id in state.amounts and amount > 0:
                state.amounts[resource_id] = amount

    # -- affordability and gates ------------------------------------------

    def can_afford(self, cost: Dict[str, float]) -> bool:
        return all(self.state.amounts.get(rid, 0.0) >= amount for rid, amount in cost.items())

    def _spend(self, cost: Dict[str, float]) -> None:
        for rid, amount in cost.items():
            self.state.amounts[rid] = max(0.0, self.state.amounts.get(rid, 0.0) - amount)

    def is_unlocked(self, gate: Unlock) -> bool:
        return self.gate_progress(gate) >= 1.0

    def gate_progress(self, gate: Unlock) -> float:
        """
        How close the player is to satisfying a gate, in [0, 1].

        Progress rather than a boolean, because the UI reveals content at partial
        progress. Seeing a locked item you are 60% of the way to is a goal;
        having it appear from nothing is a surprise.
        """
        if gate.kind == "none":
            return 1.0
        amount = max(1e-9, gate.amount)
        if gate.kind == "resource_total":
            return min(1.0, self.state.earned.get(gate.target, 0.0) / amount)
        if gate.kind == "resource_now":
            return min(1.0, self.state.amounts.get(gate.target, 0.0) / amount)
        if gate.kind == "upgrades_owned":
            return min(1.0, len(self.state.upgrades) / amount)
        if gate.kind == "family_owned":
            owned = sum(1 for uid in self.state.upgrades if self._family_of(uid) == gate.target)
            return min(1.0, owned / amount)
        if gate.kind == "upgrade_owned":
            return 1.0 if gate.target in self.state.upgrade_set else 0.0
        if gate.kind == "generators":
            return min(1.0, self.state.generators.get(gate.target, 0) / amount)
        if gate.kind == "ascensions":
            return min(1.0, self.state.ascensions / amount)
        return 1.0

    def gate_text(self, gate: Unlock) -> str:
        if gate.kind == "none":
            return ""
        if gate.kind == "resource_total":
            return f"Earn {fmt_number(gate.amount)} {self._resource_name(gate.target)} in total"
        if gate.kind == "resource_now":
            return f"Hold {fmt_number(gate.amount)} {self._resource_name(gate.target)}"
        if gate.kind == "upgrades_owned":
            return f"Own {int(gate.amount)} upgrades"
        if gate.kind == "family_owned":
            return f"Own {int(gate.amount)} {gate.target} upgrades"
        if gate.kind == "upgrade_owned":
            try:
                return f"Research {self.game.upgrade(gate.target).name}"
            except KeyError:
                return "Research a prerequisite"
        if gate.kind == "generators":
            return f"Own {int(gate.amount)} of a generator"
        if gate.kind == "ascensions":
            return f"Reach ascension {int(gate.amount)}"
        return ""

    def _resource_name(self, resource_id: str) -> str:
        try:
            return self.game.resource(resource_id).name
        except KeyError:
            return resource_id

    def upgrade_available(self, upgrade: Upgrade) -> bool:
        if not all(req in self.state.upgrade_set for req in upgrade.requires):
            return False
        return self.is_unlocked(upgrade.unlock)

    # -- presentation ------------------------------------------------------

    def effect_text(self, effect: Effect) -> str:
        """Human-readable description of one modifier."""
        target = effect.target or "*"
        everything = target == "*"

        def name_of(kind: str) -> str:
            if everything:
                return {"resource": "all resources", "action": "all actions", "generator": "all generators"}[kind]
            try:
                if kind == "resource":
                    return self.game.resource(target).name
                if kind == "action":
                    return self.game.action(target).name
                return self.game.generator(target).name
            except KeyError:
                return target

        kind, value = effect.kind, effect.value
        if kind == "global_mult":
            return f"×{value:g} to all production"
        if kind == "resource_rate":
            return f"×{value:g} {name_of('resource')} production"
        if kind == "resource_cap":
            return f"×{value:g} {name_of('resource')} storage"
        if kind == "action_yield":
            return f"×{value:g} output from {name_of('action')}"
        if kind == "generator_rate":
            return f"×{value:g} output from {name_of('generator')}"
        if kind == "generator_cost":
            return f"−{(1 - value) * 100:.0f}% cost for {name_of('generator')}"
        if kind == "cooldown":
            return f"−{(1 - value) * 100:.0f}% cooldown on {name_of('action')}"
        if kind == "decay":
            return f"−{(1 - value) * 100:.0f}% {name_of('resource')} decay"
        if kind == "crit_chance":
            mult = effect.extra.get("mult", 2.0)
            return f"+{value * 100:.1f}% chance of ×{mult:g} from {name_of('action')}"
        if kind == "start_resource":
            return f"Start each run with {fmt_number(value)} {name_of('resource')}"
        return kind

    def effects_text(self, effects: Tuple[Effect, ...]) -> str:
        return " · ".join(self.effect_text(e) for e in effects)


def _mul(table: Dict[str, float], key: str, value: float) -> None:
    table[key] = table.get(key, 1.0) * value
