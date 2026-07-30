"""
Headless balance harness.

A generated game cannot be playtested by hand. There are two billion seeds, and
the interesting failures -- a run that soft-locks at minute three, a run where the
first generator is unaffordable for twenty minutes, a run whose prestige is
reachable in ten seconds -- do not show up in the seed you happened to open.

So the game plays itself. `simulate()` runs a deliberately unclever autoplayer
against a run at arbitrary speed and reports what happened; `audit()` does that
across many seeds and flags the outliers.

The autoplayer is intentionally *not* good at the game. It buys the cheapest
thing that helps and converts when it has surplus. If a mediocre strategy can
reach prestige in a reasonable time, a player who is paying attention certainly
can -- and if a mediocre strategy stalls, the run is badly generated regardless of
what an expert could wring out of it.
"""

from __future__ import annotations

import statistics
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from .engine import GameEngine
from .generator import generate_game
from .model import GameDef

# Sim resolution. Fine enough that sub-second cooldowns behave, coarse enough
# that an hour of game time costs well under a second of wall time.
STEP = 0.25
# Clicks per second the autoplayer is allowed. A real player sustains ~4.
CLICKS_PER_SECOND = 4.0
# A generator is worth buying if it pays for itself within this many seconds.
PAYBACK_SECONDS = 180.0
# Convert only when holding this multiple of the input cost, so the autoplayer
# does not spend itself out of the resource its generators need.
CONVERT_SURPLUS = 3.0
# No purchase for this long means the run has stalled.
STALL_SECONDS = 300.0
# Minimum healthy seconds per ascension. A two-minute reset loop is fast but
# legitimate variety; anything tighter is a treadmill.
MIN_ASCENSION_SECONDS = 120.0


class FakeClock:
    """A clock the harness drives by hand. Nothing here sleeps."""

    def __init__(self, start: float = 1_000_000.0):
        self.now = start

    def __call__(self) -> float:
        return self.now

    def advance(self, seconds: float) -> None:
        self.now += seconds


@dataclass
class RunMetrics:
    """What one simulated run tells us about a seed."""

    seed: int
    title: str
    resources: int
    max_tier: int
    actions: int
    generators: int
    upgrades: int
    mechanics: List[str] = field(default_factory=list)
    seconds: float = 0.0
    actions_taken: int = 0
    # Cumulative across the whole simulation. Counting what the player *holds*
    # would read as zero on any run that prestiged, since a reset clears the tree.
    upgrades_bought: int = 0
    generators_bought: int = 0
    upgrades_held: int = 0
    generators_held: int = 0
    first_upgrade_at: Optional[float] = None
    first_generator_at: Optional[float] = None
    first_prestige_at: Optional[float] = None
    prestige_points: float = 0.0
    ascensions: int = 0
    run_score: float = 0.0
    stalled_for: float = 0.0
    resources_touched: int = 0
    throttled_generators: int = 0
    problems: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return dict(self.__dict__)


def simulate(game: GameDef, seconds: float = 1800.0, clicks_per_second: float = CLICKS_PER_SECOND) -> RunMetrics:
    """
    Play `game` for `seconds` of simulated time and report what happened.

    Returns metrics rather than asserting anything -- judgement about what counts
    as balanced belongs in `audit()` and in the tests, not in the simulator.
    """
    clock = FakeClock()
    engine = GameEngine(game, clock=clock)

    metrics = RunMetrics(
        seed=game.seed,
        title=game.title,
        resources=len(game.resources),
        max_tier=game.max_tier,
        actions=len(game.actions),
        generators=len(game.generators),
        upgrades=len(game.upgrades),
        mechanics=[m.kind for m in game.mechanics],
    )

    click_budget = 0.0
    last_purchase_at = 0.0
    elapsed = 0.0

    while elapsed < seconds:
        clock.advance(STEP)
        elapsed += STEP
        engine.advance()

        # -- act -----------------------------------------------------------
        click_budget += clicks_per_second * STEP
        while click_budget >= 1.0:
            click_budget -= 1.0
            if _best_click(engine):
                metrics.actions_taken += 1

        # What the player is saving toward. Converting or buying past this is how
        # a naive autoplayer starves itself, and a starved autoplayer reports
        # every seed as stalled.
        reserve = _reserve(engine)
        _do_converts(engine, metrics, reserve)

        # -- spend ---------------------------------------------------------
        bought = _buy_upgrades(engine, metrics, elapsed)
        bought = _buy_generators(engine, metrics, elapsed, reserve) or bought
        if bought:
            last_purchase_at = elapsed

        # -- ascend --------------------------------------------------------
        points = engine.prestige_points()
        if points >= 1.0 and metrics.first_prestige_at is None:
            metrics.first_prestige_at = elapsed
        if _should_prestige(engine, points, elapsed, metrics):
            engine.prestige()
            _spend_prestige(engine)
            metrics.ascensions = engine.state.ascensions
            last_purchase_at = elapsed

        stalled = elapsed - last_purchase_at
        metrics.stalled_for = max(metrics.stalled_for, stalled)

    metrics.seconds = elapsed
    metrics.prestige_points = engine.prestige_points()
    metrics.run_score = engine.run_score()
    metrics.upgrades_held = len(engine.state.upgrades)
    metrics.generators_held = sum(engine.state.generators.values())
    metrics.resources_touched = sum(1 for v in engine.state.lifetime.values() if v > 0)

    _, _, efficiency = engine.rates()
    metrics.throttled_generators = sum(1 for eff in efficiency.values() if eff < 0.999)

    metrics.problems = _diagnose(metrics, engine)
    return metrics


# ---------------------------------------------------------------------------
# Autoplayer
# ---------------------------------------------------------------------------


def _best_click(engine: GameEngine) -> bool:
    """Use the free action with the highest tier-weighted output."""
    best = None
    best_value = 0.0
    for action in engine.game.actions:
        if action.cost or not engine.is_unlocked(action.unlock):
            continue
        if engine.state.action_ready.get(action.id, 0.0) > engine.clock():
            continue
        value = _bundle_value(engine, engine.action_yield(action))
        if value > best_value:
            best, best_value = action, value
    if best is None:
        return False
    return engine.do_action(best.id).get("ok", False)


def _reserve(engine: GameEngine) -> Dict[str, float]:
    """
    Per-resource savings target: what the next purchase will cost.

    A player about to afford an upgrade stops spending on anything else. Without
    modelling that, the autoplayer spends its tier-0 income the instant it lands
    and never accumulates the 60 it needs, which looks exactly like a badly
    generated economy and is not.
    """
    reserve: Dict[str, float] = {}

    upgrades = [
        u
        for u in engine.game.upgrades
        if u.id not in engine.state.upgrade_set and engine.upgrade_available(u)
    ]
    if upgrades:
        cheapest = min(upgrades, key=lambda u: _bundle_value(engine, u.cost))
        for rid, amount in cheapest.cost.items():
            reserve[rid] = max(reserve.get(rid, 0.0), amount)

    target = _best_generator(engine, ignore_affordability=True)
    if target is not None:
        cost = engine.generator_cost(target.id, 1)
        rid = target.cost_resource
        reserve[rid] = max(reserve.get(rid, 0.0), cost)

    return reserve


def _do_converts(engine: GameEngine, metrics: RunMetrics, reserve: Dict[str, float]) -> None:
    """
    Push the economy up the chain, but only with genuinely spare input.

    Without converting, the autoplayer would hoard tier 0 forever and every run
    would report as stalled. Converting without a reserve does the opposite:
    it strips the resource that upgrades and generators are priced in.
    """
    for action in engine.game.actions:
        if not action.cost or not engine.is_unlocked(action.unlock):
            continue
        if engine.state.action_ready.get(action.id, 0.0) > engine.clock():
            continue
        spare = True
        for rid, amount in action.cost.items():
            held = engine.state.amounts.get(rid, 0.0) - reserve.get(rid, 0.0)
            if held < amount * CONVERT_SURPLUS:
                spare = False
                break
        if not spare:
            continue
        if engine.do_action(action.id).get("ok"):
            metrics.actions_taken += 1


def _buy_upgrades(engine: GameEngine, metrics: RunMetrics, elapsed: float) -> bool:
    """Buy every affordable upgrade, cheapest first. Upgrades are never a trap."""
    bought = False
    while True:
        candidates = [
            u
            for u in engine.game.upgrades
            if u.id not in engine.state.upgrade_set
            and engine.upgrade_available(u)
            and engine.can_afford(u.cost)
        ]
        if not candidates:
            return bought
        candidates.sort(key=lambda u: _bundle_value(engine, u.cost))
        if not engine.buy_upgrade(candidates[0].id).get("ok"):
            return bought
        bought = True
        metrics.upgrades_bought += 1
        if metrics.first_upgrade_at is None:
            metrics.first_upgrade_at = elapsed


def _best_generator(engine: GameEngine, ignore_affordability: bool = False):
    """The unlocked generator with the shortest tier-weighted payback period."""
    best = None
    best_payback = PAYBACK_SECONDS
    for generator in engine.game.generators:
        if not engine.is_unlocked(generator.unlock):
            continue
        cost = engine.generator_cost(generator.id, 1)
        if not ignore_affordability and engine.state.amounts.get(generator.cost_resource, 0.0) < cost:
            continue
        rate = generator.rate * engine.mods.multiplier(engine.mods.generator_rate, generator.id)
        value = rate * _tier_weight(engine, generator.resource)
        if value <= 0:
            continue
        payback = (cost * _tier_weight(engine, generator.cost_resource)) / value
        if payback < best_payback:
            best, best_payback = generator, payback
    return best


def _buy_generators(
    engine: GameEngine, metrics: RunMetrics, elapsed: float, reserve: Dict[str, float]
) -> bool:
    """
    Buy the best-payback affordable generator, unless an upgrade is nearly in reach.

    Upgrades are permanent and generators are not (a prestige wipes them), so a
    player close to an upgrade waits. "Nearly" is 60% of the way there.
    """
    best = _best_generator(engine)
    if best is None:
        return False

    cost = engine.generator_cost(best.id, 1)
    held = engine.state.amounts.get(best.cost_resource, 0.0)
    upgrade_target = reserve.get(best.cost_resource, 0.0)
    if upgrade_target > cost and held >= upgrade_target * 0.6:
        return False  # saving for the upgrade instead

    if not engine.buy_generator(best.id).get("ok"):
        return False
    metrics.generators_bought += 1
    if metrics.first_generator_at is None:
        metrics.first_generator_at = elapsed
    return True


def _should_prestige(engine: GameEngine, points: float, elapsed: float, metrics: RunMetrics) -> bool:
    """
    Ascend when this run has beaten the last one, not merely when it is possible.

    A greedy "reset as soon as you can" rule resets every ninety seconds and tells
    us nothing: it makes any divisor look fine and hides the case where the
    meta-loop has stopped paying. Requiring each run to approach the best run so
    far models the actual decision, and makes the ascension count in the audit a
    meaningful signal about pacing.
    """
    if points < 1.0:
        return False
    threshold = max(3.0, engine.state.best_points * 0.8)
    if points >= threshold:
        return True
    # Fallback so a run that creeps just past one point still exercises reset.
    return elapsed > 900.0 and metrics.ascensions == 0


def _spend_prestige(engine: GameEngine) -> None:
    """Spend prestige currency, cheapest first, until nothing is affordable."""
    while True:
        candidates = [
            p
            for p in engine.game.prestige_upgrades
            if engine.state.prestige_levels.get(p.id, 0) < p.max_level
            and engine.state.prestige_currency >= p.cost_at(engine.state.prestige_levels.get(p.id, 0))
        ]
        if not candidates:
            return
        candidates.sort(key=lambda p: p.cost_at(engine.state.prestige_levels.get(p.id, 0)))
        if not engine.buy_prestige_upgrade(candidates[0].id).get("ok"):
            return


def _tier_weight(engine: GameEngine, resource_id: str) -> float:
    """Value one unit of a resource by its depth in the chain."""
    try:
        return 10.0 ** engine.game.resource(resource_id).tier
    except KeyError:
        return 1.0


def _bundle_value(engine: GameEngine, bundle: Dict[str, float]) -> float:
    return sum(amount * _tier_weight(engine, rid) for rid, amount in bundle.items())


# ---------------------------------------------------------------------------
# Diagnosis
# ---------------------------------------------------------------------------


def _diagnose(metrics: RunMetrics, engine: GameEngine) -> List[str]:
    """
    Turn metrics into named problems.

    These are the failure modes that matter for a generated incremental, in
    roughly the order a player would notice them.
    """
    problems: List[str] = []

    if metrics.first_upgrade_at is None:
        problems.append("no upgrade was ever affordable")
    elif metrics.first_upgrade_at > 300.0:
        problems.append(f"first upgrade took {metrics.first_upgrade_at:.0f}s")

    if metrics.first_generator_at is None:
        problems.append("no generator was ever affordable")
    elif metrics.first_generator_at > 240.0:
        problems.append(f"first generator took {metrics.first_generator_at:.0f}s")

    if metrics.first_prestige_at is None:
        problems.append("prestige never became available")
    elif metrics.first_prestige_at < 60.0:
        problems.append(f"prestige available after only {metrics.first_prestige_at:.0f}s")

    # A reset loop tighter than this is a treadmill, not a decision. This check
    # exists because an 84-ascension run once passed every other assertion here.
    if metrics.ascensions > max(1.0, metrics.seconds / MIN_ASCENSION_SECONDS):
        problems.append(
            f"ascended {metrics.ascensions} times in {metrics.seconds / 60:.0f}min "
            f"(loop is ~{metrics.seconds / max(1, metrics.ascensions):.0f}s)"
        )

    if metrics.stalled_for > STALL_SECONDS:
        problems.append(f"stalled for {metrics.stalled_for:.0f}s with nothing to buy")

    if metrics.upgrades_bought == 0:
        problems.append("bought no upgrades at all")

    if metrics.resources_touched < 2:
        problems.append("never produced a second resource")

    # A run where the autoplayer bought the entire tree in one sitting has
    # nothing left to offer; the numbers are too generous.
    if metrics.upgrades_held >= metrics.upgrades:
        problems.append("entire upgrade tree bought within the window")

    return problems


# ---------------------------------------------------------------------------
# Audit across seeds
# ---------------------------------------------------------------------------


def audit(
    seeds: List[int],
    seconds: float = 1800.0,
    clicks_per_second: float = CLICKS_PER_SECOND,
) -> Dict[str, Any]:
    """
    Simulate many seeds and summarise. Used by the CLI and by the balance tests.

    The summary reports medians rather than means: one pathological seed should
    not be able to hide behind an average, and the whole point is to find the
    pathological seeds.
    """
    runs: List[RunMetrics] = []
    failures: List[Dict[str, Any]] = []

    for seed in seeds:
        game = generate_game(seed)
        metrics = simulate(game, seconds=seconds, clicks_per_second=clicks_per_second)
        runs.append(metrics)
        if metrics.problems:
            failures.append({"seed": seed, "title": metrics.title, "problems": metrics.problems})

    return {
        "seeds": len(seeds),
        "seconds": seconds,
        "healthy": len(runs) - len(failures),
        "failures": failures,
        "medians": {
            "resources": _median([r.resources for r in runs]),
            "max_tier": _median([r.max_tier for r in runs]),
            "upgrades_bought": _median([r.upgrades_bought for r in runs]),
            "generators_bought": _median([r.generators_bought for r in runs]),
            "first_upgrade_at": _median([r.first_upgrade_at for r in runs if r.first_upgrade_at]),
            "first_generator_at": _median([r.first_generator_at for r in runs if r.first_generator_at]),
            "first_prestige_at": _median([r.first_prestige_at for r in runs if r.first_prestige_at]),
            "prestige_points": _median([r.prestige_points for r in runs]),
            "ascensions": _median([r.ascensions for r in runs]),
        },
        "mechanic_frequency": _frequency([kind for r in runs for kind in r.mechanics]),
    }


def _median(values: List[float]) -> Optional[float]:
    numeric = [v for v in values if v is not None]
    if not numeric:
        return None
    return round(float(statistics.median(numeric)), 2)


def _frequency(items: List[str]) -> Dict[str, int]:
    counts: Dict[str, int] = {}
    for item in items:
        counts[item] = counts.get(item, 0) + 1
    return dict(sorted(counts.items(), key=lambda kv: -kv[1]))
