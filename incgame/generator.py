"""
Procedural generation of a complete run.

`generate_game(seed)` is a pure function of its seed: same seed in, byte-identical
`GameDef` out. Nothing here reads the clock, the environment, or the global RNG.

The generation order matters, because each phase is allowed to depend only on the
phases before it:

    1. theme + title        cosmetics, and the palette later phases draw from
    2. resources            a conversion chain, tier 0 upward
    3. actions              manual verbs: free clicks, then refining converts
    4. generators           passive production, one or two per resource
    5. upgrades             families of modifiers across five cost tiers
    6. mechanics            emergent systems wired to the content above
    7. prestige             reset currency and the permanent upgrades

Balance lives in `TUNING`. Rebalancing the game means editing numbers there and
re-running `python -m incgame balance`, never editing a specific seed.
"""

from __future__ import annotations

import random
from dataclasses import replace
from typing import Any, Dict, List, Optional, Tuple

from . import names as N
from .model import (
    Action,
    Effect,
    GameDef,
    Generator,
    Mechanic,
    NO_GATE,
    PrestigeUpgrade,
    Resource,
    Unlock,
    Upgrade,
)
from .rng import Namer, hue_palette, jitter, pick, pick_n, round_nice, slug, theme, weighted

# ---------------------------------------------------------------------------
# Tuning
# ---------------------------------------------------------------------------

TUNING: Dict[str, Any] = {
    # How many resources, and therefore how deep the conversion chain runs.
    "resources_min": 3,
    "resources_max": 6,
    # Manual actions.
    "click_actions": (1, 2),
    "converts_per_tier": (1, 2),
    "click_yield": (0.8, 1.4),
    "convert_ratio": (6.0, 14.0),  # lower-tier spent per 1 higher-tier gained
    "convert_cooldown": (0.25, 1.5),
    # Generators. Rates fall off per tier because higher tiers are worth more.
    "generators_per_resource": (1, 2),
    "gen_rate_tier0": (0.25, 1.1),
    # Rate multiplier per tier above 0. Conversions run 6-14 lower-tier units per
    # upper-tier unit, so a falloff near 1/6 is roughly "fair" -- but at 0.16 a
    # tier-4 generator produced 0.0004/s, which is one unit per forty minutes and
    # therefore dead content on any deep seed. 0.22 keeps deep tiers worth
    # building; the depth-scaled prestige divisor absorbs the faster scoring.
    "gen_rate_falloff": 0.22,
    "gen_base_cost_tier0": (10.0, 30.0),
    "gen_cost_growth": (1.12, 1.21),
    "gen_upkeep_chance": 0.55,  # chance a tier>=1 generator eats its input
    "gen_upkeep_fraction": (0.15, 0.6),  # of its own output rate, in lower tier
    # Upgrades.
    "upgrade_families": (3, 5),
    "upgrade_tiers": 5,
    "upgrades_per_tier": (6, 12),
    # What one upgrade costs, per tier of the resource paying for it.
    # Raised from [60, 25, 10, 6, 4, 3] once upgrade effects started targeting
    # content at the player's own depth (see _target_for_tier). The effects did not
    # get numerically stronger; they stopped being wasted on resources the player
    # had not reached, which is roughly a 40% real power increase.
    "cost_unit_by_tier": [108.0, 45.0, 18.0, 11.0, 7.0, 5.0],
    # Per upgrade tier above the paying resource's tier. Raised from 2.6: at that
    # value the top of the tree was barely dearer than the middle, and ~14% of
    # seeds had their entire upgrade tree bought inside twenty minutes. 3.4 makes
    # late tiers a real commitment and cuts that to ~5% with no other regression.
    "cost_tier_step": 3.4,
    # Unlock thresholds, in the same per-tier units as costs (see _resource_gate).
    "gate_tier_step": 2.2,
    "gate_unit_scale": 1.5,
    "requires_chance": 0.55,
    # Emergent mechanics.
    "mechanics": (2, 4),
    # Scarcity: which tiers may decay, and how fast.
    "decay_chance": 0.45,
    "decay_rate": (0.004, 0.02),  # fraction per second
    # Prestige.
    "prestige_upgrades": (6, 9),
    # Prestige cost scales with the depth of the generated chain. Run score
    # weights each resource by 10^tier (see engine.run_score), so a five-tier
    # economy racks up score an order of magnitude faster than a two-tier one. A
    # flat divisor therefore made deep seeds prestige every 45 seconds and shallow
    # seeds barely prestige at all -- the same number meaning two different games.
    "prestige_divisor": 3800.0,
    "prestige_depth_scale": 0.9,  # added per tier of chain depth
    # Geometric growth factor on the score needed per prestige point, applied per
    # ascension. Must be able to race compounding permanent multipliers; see
    # engine.prestige_requirement. Too low and the loop collapses to seconds, too
    # high and the meta-game dies after a handful of resets.
    "prestige_escalation": (1.7, 2.2),
}

# Effect kinds each upgrade family leans toward. Families read as schools of
# thought rather than random grab-bags, which is what makes synergy mechanics
# ("own 5 of this family") feel like a decision instead of a coincidence.
FAMILY_SPECIALTIES = ["action", "generator", "resource", "capacity", "efficiency", "critical"]


def random_seed() -> int:
    """A fresh seed for a new run. The only nondeterminism in the package."""
    return random.SystemRandom().randrange(1, 2**31 - 1)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def generate_game(seed: int) -> GameDef:
    """Generate a complete, validated run definition from `seed`."""
    seed = int(seed)
    rng = random.Random(seed)
    namer = Namer(rng)

    run_theme = theme(rng)
    title = "The " + namer.unique(N.ADJECTIVES, N.TITLE_NOUNS)
    flavor = pick(rng, N.FLAVOUR_OPENINGS) + " " + pick(rng, N.FLAVOUR_CLOSINGS)

    resources = _gen_resources(rng, namer)
    actions = _gen_actions(rng, namer, resources)
    generators = _gen_generators(rng, namer, resources)
    upgrades = _gen_upgrades(rng, namer, resources, actions, generators)
    upgrades, actions, generators = _wire_unlock_upgrade(rng, upgrades, actions, generators)
    mechanics = _gen_mechanics(rng, namer, resources, actions, upgrades)
    resources = _apply_scarcity(resources, mechanics)
    prestige_name, prestige_color, prestige_upgrades = _gen_prestige(rng, namer, resources, run_theme)

    max_tier = max(r.tier for r in resources)
    divisor = TUNING["prestige_divisor"] * (1.0 + TUNING["prestige_depth_scale"] * max_tier)

    game = GameDef(
        seed=seed,
        title=title,
        flavor=flavor,
        theme=run_theme,
        resources=tuple(resources),
        actions=tuple(actions),
        generators=tuple(generators),
        upgrades=tuple(upgrades),
        mechanics=tuple(mechanics),
        prestige_name=prestige_name,
        prestige_color=prestige_color,
        prestige_upgrades=tuple(prestige_upgrades),
        prestige_divisor=round_nice(jitter(rng, divisor, 0.3)),
        prestige_escalation=round(rng.uniform(*TUNING["prestige_escalation"]), 3),
    )
    validate_game(game)
    return game


# ---------------------------------------------------------------------------
# Phase 2: resources
# ---------------------------------------------------------------------------


def _gen_resources(rng: random.Random, namer: Namer) -> List[Resource]:
    count = rng.randint(TUNING["resources_min"], TUNING["resources_max"])
    tiers = _tier_shape(rng, count)
    palette = hue_palette(rng, count)

    resources: List[Resource] = []
    for index, tier in enumerate(tiers):
        # Tier 0 gets a plain noun; refined tiers get an adjective, so the chain
        # reads as raw material -> product without needing a tooltip.
        if tier == 0:
            name = namer.unique(N.RESOURCE_NOUNS)
        else:
            name = namer.unique(N.ADJECTIVES, N.RESOURCE_NOUNS)
        cap = _resource_cap(rng, tier)
        resources.append(
            Resource(
                id=slug(name),
                name=name,
                color=palette[index],
                description=pick(rng, N.RESOURCE_DESCRIPTIONS),
                tier=tier,
                base_rate=0.0,
                cap=cap,
            )
        )
    return resources


def _tier_shape(rng: random.Random, count: int) -> List[int]:
    """
    Decide the shape of the conversion chain.

    Always at least one tier-0 resource. Sometimes two resources share a tier,
    which produces a branching economy (two parallel refinements competing for
    the same input) rather than a single ladder.
    """
    tiers = [0]
    current = 0
    for _ in range(count - 1):
        # Branch (stay at this tier) or deepen. Deepening is more likely so runs
        # get a real progression ladder, but branches keep some runs wide.
        if current > 0 and rng.random() < 0.28:
            tiers.append(current)
        else:
            current += 1
            tiers.append(current)
    return tiers


def _resource_cap(rng: random.Random, tier: int) -> float:
    """Caps exist to make storage upgrades meaningful; some resources have none."""
    if rng.random() < 0.35:
        return float("inf")
    base = 2000.0 / (4.0**tier)
    return round_nice(jitter(rng, max(25.0, base), 0.35))


# ---------------------------------------------------------------------------
# Phase 3: actions
# ---------------------------------------------------------------------------


def _gen_actions(rng: random.Random, namer: Namer, resources: List[Resource]) -> List[Action]:
    actions: List[Action] = []
    base = [r for r in resources if r.tier == 0]

    # Free clicks on tier-0 resources. These are never gated -- a run must be
    # playable from the first frame with nothing owned.
    click_count = rng.randint(*TUNING["click_actions"])
    for index in range(click_count):
        resource = base[index % len(base)]
        name = namer.unique(N.ACTION_VERBS, [resource.name])
        actions.append(
            Action(
                id=slug(name),
                name=name,
                description=pick(rng, N.ACTION_DESCRIPTIONS),
                kind="click",
                cost={},
                output={resource.id: round_nice(jitter(rng, rng.uniform(*TUNING["click_yield"]), 0.2))},
                cooldown=0.0,
                unlock=NO_GATE,
            )
        )

    # Converts: spend the tier below, gain this tier. This is the spine of the
    # economy -- without them, higher tiers are unreachable by hand.
    by_tier: Dict[int, List[Resource]] = {}
    for resource in resources:
        by_tier.setdefault(resource.tier, []).append(resource)

    for tier in sorted(t for t in by_tier if t > 0):
        inputs = by_tier.get(tier - 1) or by_tier[min(by_tier)]
        for resource in by_tier[tier]:
            for _ in range(rng.randint(*TUNING["converts_per_tier"])):
                source = pick(rng, inputs)
                ratio = round_nice(jitter(rng, rng.uniform(*TUNING["convert_ratio"]), 0.2))
                gain = round_nice(jitter(rng, 1.0, 0.25))
                name = namer.unique(N.ACTION_VERBS, [resource.name])
                actions.append(
                    Action(
                        id=slug(name),
                        name=name,
                        description=pick(rng, N.ACTION_DESCRIPTIONS),
                        kind="convert",
                        cost={source.id: ratio},
                        output={resource.id: gain},
                        cooldown=round(rng.uniform(*TUNING["convert_cooldown"]), 2),
                        unlock=Unlock("resource_total", source.id, round_nice(ratio * rng.uniform(2.0, 6.0))),
                    )
                )
    return actions


# ---------------------------------------------------------------------------
# Phase 4: generators
# ---------------------------------------------------------------------------


def _gen_generators(rng: random.Random, namer: Namer, resources: List[Resource]) -> List[Generator]:
    generators: List[Generator] = []
    by_tier: Dict[int, List[Resource]] = {}
    for resource in resources:
        by_tier.setdefault(resource.tier, []).append(resource)

    for resource in resources:
        for _ in range(rng.randint(*TUNING["generators_per_resource"])):
            name = namer.unique(N.ADJECTIVES, N.GENERATOR_NOUNS)
            rate = rng.uniform(*TUNING["gen_rate_tier0"]) * (TUNING["gen_rate_falloff"] ** resource.tier)
            rate = float(f"{jitter(rng, rate, 0.25):.4g}")

            # Generators are bought with the tier below what they make, which
            # keeps every purchase a real trade-off against manual converting.
            lower = by_tier.get(resource.tier - 1)
            cost_resource = pick(rng, lower) if lower else resource
            cost_scale = TUNING["cost_unit_by_tier"][min(cost_resource.tier, 5)] / TUNING["cost_unit_by_tier"][0]
            base_cost = round_nice(
                jitter(rng, rng.uniform(*TUNING["gen_base_cost_tier0"]) * max(0.15, cost_scale) * 2.5, 0.3)
            )

            upkeep: Dict[str, float] = {}
            if resource.tier > 0 and lower and rng.random() < TUNING["gen_upkeep_chance"]:
                feed = pick(rng, lower)
                upkeep[feed.id] = float(f"{rate * rng.uniform(*TUNING['gen_upkeep_fraction']) * 8:.4g}")

            gate: Unlock = NO_GATE
            if resource.tier > 0 or generators:
                gate_target = cost_resource.id
                gate = Unlock("resource_total", gate_target, round_nice(base_cost * rng.uniform(0.6, 1.4)))

            generators.append(
                Generator(
                    id=slug(name),
                    name=name,
                    description=pick(rng, N.GENERATOR_DESCRIPTIONS),
                    resource=resource.id,
                    rate=rate,
                    cost_resource=cost_resource.id,
                    base_cost=base_cost,
                    cost_growth=round(rng.uniform(*TUNING["gen_cost_growth"]), 3),
                    upkeep=upkeep,
                    unlock=gate,
                )
            )

    # The very first generator must be reachable immediately, or the run stalls
    # on manual clicking with nothing to spend on.
    for index, generator in enumerate(generators):
        if generator.resource in {r.id for r in by_tier[0]}:
            generators[index] = replace(generator, unlock=NO_GATE)
            break
    return generators


# ---------------------------------------------------------------------------
# Phase 5: upgrades
# ---------------------------------------------------------------------------


def _gen_upgrades(
    rng: random.Random,
    namer: Namer,
    resources: List[Resource],
    actions: List[Action],
    generators: List[Generator],
) -> List[Upgrade]:
    family_count = rng.randint(*TUNING["upgrade_families"])
    family_names = pick_n(rng, N.FAMILY_NAMES, family_count)
    specialties = {name: pick(rng, FAMILY_SPECIALTIES) for name in family_names}

    max_tier = max(r.tier for r in resources)
    upgrades: List[Upgrade] = []
    by_family: Dict[str, List[Upgrade]] = {name: [] for name in family_names}

    for tier in range(TUNING["upgrade_tiers"]):
        for _ in range(rng.randint(*TUNING["upgrades_per_tier"])):
            family = pick(rng, family_names)
            name = namer.unique(N.ADJECTIVES, N.UPGRADE_NOUNS)
            effects = _gen_effects(rng, specialties[family], tier, resources, actions, generators)
            cost = _upgrade_cost(rng, tier, max_tier, resources)

            gate: Unlock = NO_GATE
            if tier > 0:
                gate = weighted(
                    rng,
                    {
                        Unlock("upgrades_owned", "", float(2 + 3 * tier)): 2.0,
                        Unlock("family_owned", family, float(1 + tier)): 1.0,
                        _resource_gate(rng, tier, max_tier, resources): 1.5,
                    },
                )

            upgrade = Upgrade(
                id=slug(name),
                name=name,
                description=pick(rng, N.UPGRADE_DESCRIPTIONS),
                family=family,
                tier=tier,
                cost=cost,
                effects=effects,
                requires=(),
                unlock=gate,
            )
            upgrades.append(upgrade)
            by_family[family].append(upgrade)

    return _chain_requirements(rng, upgrades, by_family)


def _resource_gate(
    rng: random.Random, tier: int, max_tier: int, resources: List[Resource]
) -> Unlock:
    """
    Build a "earn N of X" gate whose N is scaled to the tier of X.

    Scaling the threshold by the upgrade's tier alone is wrong, and wrong in a way
    that only shows up on deep seeds: 9,720 is a fine target for a tier-0 resource
    you make one per click, and unreachable for a tier-4 resource that caps at 25
    and trickles in at 0.0004/s. The upgrade then hides forever and the run
    silently loses a chunk of its tree. Pricing the gate in the same units as the
    costs keeps it proportionate at every depth.
    """
    want_tier = min(max_tier, rng.randint(0, tier))
    candidates = [r for r in resources if r.tier == want_tier] or resources
    resource = pick(rng, candidates)
    unit = TUNING["cost_unit_by_tier"][min(resource.tier, 5)]
    amount = unit * (TUNING["gate_tier_step"] ** tier) * TUNING["gate_unit_scale"]
    return Unlock("resource_total", resource.id, round_nice(jitter(rng, amount, 0.25)))


def _upgrade_cost(
    rng: random.Random, tier: int, max_tier: int, resources: List[Resource]
) -> Dict[str, float]:
    """
    Price an upgrade in whichever resource tier suits its own tier.

    Higher-tier upgrades are paid for in higher-tier resources, whose numbers are
    naturally smaller and harder-won. The `cost_tier_step` term prices the gap
    when a late upgrade is still paid for in an early resource.
    """
    want_tier = min(max_tier, max(0, tier - rng.choice([0, 0, 1])))
    candidates = [r for r in resources if r.tier == want_tier] or resources
    resource = pick(rng, candidates)
    unit = TUNING["cost_unit_by_tier"][min(resource.tier, 5)]
    amount = unit * (TUNING["cost_tier_step"] ** max(0, tier - resource.tier))
    return {resource.id: round_nice(jitter(rng, amount, 0.3))}


def _gen_effects(
    rng: random.Random,
    specialty: str,
    tier: int,
    resources: List[Resource],
    actions: List[Action],
    generators: List[Generator],
) -> Tuple[Effect, ...]:
    """
    Build the modifier payload for one upgrade.

    Strength scales with tier so late upgrades feel like late upgrades, and a
    high-tier upgrade sometimes carries a second effect so the top of a tree has
    standout purchases.

    Two deliberate departures from "just use the family's specialty":

    * Tier 0 never gets a probabilistic effect. The first upgrade a player buys
      has to teach them that upgrades do something, and "+4% chance of ×3.6" is
      unreadable at that point -- you cannot feel it, and you cannot verify it.
    * The specialty holds only ~70% of the time. At 100%, three cards from one
      family sit next to each other in the list reading almost identically, which
      makes a 45-upgrade tree feel like a 6-upgrade tree.
    """
    if tier == 0:
        specialty = pick(rng, ["action", "generator", "resource"])
    elif rng.random() < 0.3:
        specialty = pick(rng, FAMILY_SPECIALTIES)

    strength = 1.0 + 0.12 * tier
    effects: List[Effect] = [_one_effect(rng, specialty, tier, strength, resources, actions, generators)]
    if tier >= 2 and rng.random() < 0.3:
        other = pick(rng, FAMILY_SPECIALTIES)
        effects.append(_one_effect(rng, other, tier, strength * 0.7, resources, actions, generators))
    if tier >= 3 and rng.random() < 0.18:
        effects.append(Effect("global_mult", "", _gain(rng, 1.06 + 0.02 * tier)))
    return tuple(effects)


MIN_UPGRADE_GAIN = 1.08


def _gain(rng: random.Random, base: float) -> float:
    """
    Roll a multiplier that is always worth buying.

    `jitter` alone put 3.6% of generated multipliers *below* 1.0 -- upgrades you
    could pay for and be worse off -- and another 3.4% under +5%, which no player
    can perceive. Both break the contract that an upgrade is never a trap, which
    the player assumes and the autoplayer relies on when it buys cheapest-first.
    """
    return round(max(MIN_UPGRADE_GAIN, jitter(rng, base, 0.2)), 3)


def _target_for_tier(rng: random.Random, tier: int, candidates: List[Any], tier_of) -> Any:
    """
    Pick a target the player can plausibly already have.

    A tier-0 upgrade that boosts storage of a tier-3 resource is not wrong, but it
    is unreadable and unfelt at the moment it is offered -- and it is the first
    thing a new run shows you. Preferring shallow targets for shallow upgrades
    makes early purchases legible; the pool widens as tiers climb.
    """
    reachable = [c for c in candidates if tier_of(c) <= tier + 1]
    return pick(rng, reachable or candidates)


def _one_effect(
    rng: random.Random,
    specialty: str,
    tier: int,
    strength: float,
    resources: List[Resource],
    actions: List[Action],
    generators: List[Generator],
) -> Effect:
    wildcard = rng.random() < 0.25  # "all actions" instead of one named action

    def resource_tier(resource: Resource) -> int:
        return resource.tier

    def output_tier(item) -> int:
        # An action or generator is as deep as the resource it produces.
        outputs = item.output if hasattr(item, "output") else {item.resource: 1}
        tiers = [r.tier for r in resources if r.id in outputs]
        return max(tiers) if tiers else 0

    if specialty == "action" and actions:
        target = "*" if wildcard else _target_for_tier(rng, tier, actions, output_tier).id
        return Effect("action_yield", target, _gain(rng, 1.2 * strength))

    if specialty == "generator" and generators:
        target = "*" if wildcard else _target_for_tier(rng, tier, generators, output_tier).id
        return Effect("generator_rate", target, _gain(rng, 1.25 * strength))

    if specialty == "resource":
        target = "*" if wildcard else _target_for_tier(rng, tier, resources, resource_tier).id
        return Effect("resource_rate", target, _gain(rng, 1.3 * strength))

    if specialty == "capacity":
        capped = [r for r in resources if r.cap != float("inf")]
        if capped:
            target = _target_for_tier(rng, tier, capped, resource_tier)
            return Effect("resource_cap", target.id, _gain(rng, 1.8 + 0.3 * tier))
        target = _target_for_tier(rng, tier, resources, resource_tier)
        return Effect("resource_rate", target.id, _gain(rng, 1.25 * strength))

    if specialty == "efficiency":
        # Reductions: multipliers below 1. Floored so stacking cannot reach zero.
        if generators and rng.random() < 0.5:
            target = "*" if wildcard else pick(rng, generators).id
            return Effect("generator_cost", target, round(1.0 - min(0.14, 0.05 + 0.015 * tier), 3))
        cooldowns = [a for a in actions if a.cooldown > 0]
        if cooldowns:
            return Effect("cooldown", pick(rng, cooldowns).id, round(1.0 - min(0.3, 0.1 + 0.04 * tier), 3))
        return Effect("generator_rate", "*", _gain(rng, 1.15 * strength))

    if specialty == "critical" and actions:
        target = "*" if wildcard else pick(rng, actions).id
        return Effect(
            "crit_chance",
            target,
            round(min(0.3, jitter(rng, 0.04 + 0.015 * tier, 0.25)), 4),
            {"mult": round(jitter(rng, 3.0 + tier, 0.3), 2)},
        )

    return Effect("global_mult", "", _gain(rng, 1.05 + 0.015 * tier))


def _chain_requirements(
    rng: random.Random, upgrades: List[Upgrade], by_family: Dict[str, List[Upgrade]]
) -> List[Upgrade]:
    """
    Turn flat upgrade lists into shallow trees.

    Requirements only ever point at a *lower* tier in the same family, which
    makes cycles and unreachable branches structurally impossible rather than
    something to test for.
    """
    replacements: Dict[str, Upgrade] = {}
    for members in by_family.values():
        ordered = sorted(members, key=lambda u: u.tier)
        for index, upgrade in enumerate(ordered):
            if index == 0 or upgrade.tier == 0:
                continue
            earlier = [u for u in ordered[:index] if u.tier < upgrade.tier]
            if earlier and rng.random() < TUNING["requires_chance"]:
                parent = pick(rng, earlier)
                replacements[upgrade.id] = replace(upgrade, requires=(parent.id,))
    return [replacements.get(u.id, u) for u in upgrades]


def _wire_unlock_upgrade(
    rng: random.Random,
    upgrades: List[Upgrade],
    actions: List[Action],
    generators: List[Generator],
) -> Tuple[List[Upgrade], List[Action], List[Generator]]:
    """
    Make one piece of content unlockable by research instead of by threshold.

    Discovering a new verb because you bought a technique reads better than
    discovering it because a counter ticked over. Only tier-0 upgrades are used
    as the key, so the unlock can never end up gated behind the thing it unlocks.
    """
    keys = [u for u in upgrades if u.tier == 0 and u.unlock.kind == "none"]
    if not keys:
        return upgrades, actions, generators

    gated_actions = [a for a in actions if a.kind == "convert"]
    gated_generators = [g for g in generators if g.unlock.kind != "none"]
    if not gated_actions and not gated_generators:
        return upgrades, actions, generators

    key = pick(rng, keys)
    gate = Unlock("upgrade_owned", key.id, 1.0)

    if gated_actions and (not gated_generators or rng.random() < 0.5):
        target = pick(rng, gated_actions)
        actions = [replace(a, unlock=gate) if a.id == target.id else a for a in actions]
    else:
        target = pick(rng, gated_generators)
        generators = [
            replace(g, unlock=gate) if g.id == target.id else g for g in generators
        ]

    described = replace(key, description=f"Working notes that make {target.name} possible.")
    upgrades = [described if u.id == key.id else u for u in upgrades]
    return upgrades, actions, generators


# ---------------------------------------------------------------------------
# Phase 6: emergent mechanics
# ---------------------------------------------------------------------------


def _gen_mechanics(
    rng: random.Random,
    namer: Namer,
    resources: List[Resource],
    actions: List[Action],
    upgrades: List[Upgrade],
) -> List[Mechanic]:
    """
    Pick and wire the run's emergent systems.

    Each mechanic is generic; what makes it interesting is which generated
    content it lands on. "Every 7th click doubles" is a rule. "Every 7th click of
    the action that feeds your only decaying resource doubles" is a strategy.
    """
    builders = {
        "synergy": _mech_synergy,
        "cascade": _mech_cascade,
        "overflow": _mech_overflow,
        "momentum": _mech_momentum,
        "resonance": _mech_resonance,
        "symbiosis": _mech_symbiosis,
        "scarcity": _mech_scarcity,
    }
    wanted = rng.randint(*TUNING["mechanics"])
    kinds = pick_n(rng, list(builders), len(builders))

    mechanics: List[Mechanic] = []
    for kind in kinds:
        if len(mechanics) >= wanted:
            break
        built = builders[kind](rng, namer, resources, actions, upgrades)
        if built is not None:
            mechanics.append(built)
    return mechanics


def _mech_name(rng: random.Random, namer: Namer) -> str:
    return namer.unique(N.ADJECTIVES, N.UPGRADE_NOUNS)


def _mech_synergy(rng, namer, resources, actions, upgrades) -> Optional[Mechanic]:
    families = sorted({u.family for u in upgrades})
    if not families:
        return None
    family = pick(rng, families)
    per = round(jitter(rng, 0.06, 0.4), 4)
    kind = pick(rng, ["global_mult", "action_yield", "generator_rate"])
    name = _mech_name(rng, namer)
    label = {"global_mult": "all production", "action_yield": "every action", "generator_rate": "every generator"}[kind]
    return Mechanic(
        id=slug(name),
        kind="synergy",
        name=name,
        description=f"Each {family} upgrade you own raises {label} by {per * 100:.1f}%.",
        params={"family": family, "per": per, "effect_kind": kind, "target": "*"},
    )


def _mech_cascade(rng, namer, resources, actions, upgrades) -> Optional[Mechanic]:
    if len(actions) < 2:
        return None
    source, other = pick_n(rng, actions, 2)
    chance = round(jitter(rng, 0.12, 0.4), 4)
    name = _mech_name(rng, namer)
    return Mechanic(
        id=slug(name),
        kind="cascade",
        name=name,
        description=(
            f"{chance * 100:.0f}% of the time, {source.name} also triggers "
            f"{other.name} for free -- cost and cooldown ignored."
        ),
        params={"action": source.id, "other_action": other.id, "chance": chance, "mult": 1.0},
    )


def _mech_overflow(rng, namer, resources, actions, upgrades) -> Optional[Mechanic]:
    capped = [r for r in resources if r.cap != float("inf")]
    if not capped or len(resources) < 2:
        return None
    source = pick(rng, capped)
    targets = [r for r in resources if r.id != source.id]
    dest = pick(rng, targets)
    ratio = round(jitter(rng, 0.08, 0.5), 4)
    name = _mech_name(rng, namer)
    return Mechanic(
        id=slug(name),
        kind="overflow",
        name=name,
        description=(
            f"{source.name} past its cap is not lost: it spills into {dest.name} "
            f"at {ratio:.3f} per unit."
        ),
        params={"source": source.id, "dest": dest.id, "ratio": ratio},
    )


def _mech_momentum(rng, namer, resources, actions, upgrades) -> Optional[Mechanic]:
    window = round(rng.uniform(1.2, 3.0), 2)
    per_click = round(jitter(rng, 0.04, 0.4), 4)
    max_stacks = rng.randint(10, 40)
    name = _mech_name(rng, namer)
    return Mechanic(
        id=slug(name),
        kind="momentum",
        name=name,
        description=(
            f"Consecutive actions within {window:.1f}s stack +{per_click * 100:.1f}% output, "
            f"up to {max_stacks} stacks. Pausing resets it."
        ),
        params={"window": window, "per_click": per_click, "max_stacks": max_stacks},
    )


def _mech_resonance(rng, namer, resources, actions, upgrades) -> Optional[Mechanic]:
    every_n = rng.randint(5, 13)
    mult = round(jitter(rng, 4.0, 0.35), 2)
    name = _mech_name(rng, namer)
    return Mechanic(
        id=slug(name),
        kind="resonance",
        name=name,
        description=f"Every {every_n}th action pays out x{mult:.1f}.",
        params={"every_n": every_n, "mult": mult},
    )


def _mech_symbiosis(rng, namer, resources, actions, upgrades) -> Optional[Mechanic]:
    if len(resources) < 2:
        return None
    target, driver = pick_n(rng, resources, 2)
    coeff = round(jitter(rng, 0.18, 0.4), 4)
    name = _mech_name(rng, namer)
    return Mechanic(
        id=slug(name),
        kind="symbiosis",
        name=name,
        description=(
            f"{target.name} production scales with how much {driver.name} you are "
            f"holding: +{coeff * 100:.0f}% per order of magnitude."
        ),
        params={"resource": target.id, "driver": driver.id, "coeff": coeff},
    )


def _mech_scarcity(rng, namer, resources, actions, upgrades) -> Optional[Mechanic]:
    # Only refined resources decay. A decaying tier-0 resource makes the opening
    # minute feel broken rather than tense.
    candidates = [r for r in resources if r.tier > 0]
    if not candidates or rng.random() > TUNING["decay_chance"]:
        return None
    resource = pick(rng, candidates)
    rate = round(rng.uniform(*TUNING["decay_rate"]), 5)
    name = _mech_name(rng, namer)
    return Mechanic(
        id=slug(name),
        kind="scarcity",
        name=name,
        description=(
            f"{resource.name} will not sit still: it loses {rate * 100:.2f}% of itself "
            f"every second. Spend it or lose it."
        ),
        params={"resource": resource.id, "decay": rate},
    )


def _apply_scarcity(resources: List[Resource], mechanics: List[Mechanic]) -> List[Resource]:
    """Fold generated scarcity mechanics back into the resources they describe."""
    decays = {m.params["resource"]: m.params["decay"] for m in mechanics if m.kind == "scarcity"}
    if not decays:
        return resources
    return [
        replace(r, decay=decays[r.id]) if r.id in decays else r for r in resources
    ]


# ---------------------------------------------------------------------------
# Phase 7: prestige
# ---------------------------------------------------------------------------


def _gen_prestige(
    rng: random.Random, namer: Namer, resources: List[Resource], run_theme: Dict[str, str]
) -> Tuple[str, str, List[PrestigeUpgrade]]:
    currency = namer.unique(N.ADJECTIVES, N.PRESTIGE_NOUNS)
    count = rng.randint(*TUNING["prestige_upgrades"])
    base = [r for r in resources if r.tier == 0]

    upgrades: List[PrestigeUpgrade] = []

    # Every run gets one repeatable global multiplier. It is the backbone of
    # meta-progression: always worth something, never the only thing worth buying.
    spine_name = namer.unique(N.ADJECTIVES, N.UPGRADE_NOUNS)
    upgrades.append(
        PrestigeUpgrade(
            id=slug(spine_name),
            name=spine_name,
            description="Permanently raises all production. Buy it again as often as you can.",
            base_cost=1.0,
            effects=(Effect("global_mult", "", _gain(rng, 1.12)),),
            max_level=50,
            cost_growth=round(rng.uniform(1.45, 1.75), 3),
        )
    )

    # And one head start, so a fresh run after prestige does not begin with the
    # same bare-hands minute every single time.
    if base:
        head_start = pick(rng, base)
        start_name = namer.unique(N.ADJECTIVES, N.UPGRADE_NOUNS)
        upgrades.append(
            PrestigeUpgrade(
                id=slug(start_name),
                name=start_name,
                description=f"Begin each run holding {head_start.name}.",
                base_cost=2.0,
                effects=(Effect("start_resource", head_start.id, round_nice(jitter(rng, 60.0, 0.3))),),
                max_level=25,
                cost_growth=round(rng.uniform(1.5, 1.9), 3),
            )
        )

    specialties = ["action", "generator", "resource", "efficiency", "critical", "capacity"]
    while len(upgrades) < count:
        name = namer.unique(N.ADJECTIVES, N.UPGRADE_NOUNS)
        specialty = pick(rng, specialties)
        repeatable = rng.random() < 0.5
        effect = _prestige_effect(rng, specialty, resources)
        upgrades.append(
            PrestigeUpgrade(
                id=slug(name),
                name=name,
                description=pick(rng, N.UPGRADE_DESCRIPTIONS),
                base_cost=round_nice(jitter(rng, rng.uniform(2.0, 25.0), 0.3)),
                effects=(effect,),
                max_level=rng.randint(5, 20) if repeatable else 1,
                cost_growth=round(rng.uniform(1.35, 1.8), 3) if repeatable else 1.0,
            )
        )
    return currency, run_theme["secondary"], upgrades


def _prestige_effect(rng: random.Random, specialty: str, resources: List[Resource]) -> Effect:
    if specialty == "action":
        return Effect("action_yield", "*", _gain(rng, 1.25))
    if specialty == "generator":
        return Effect("generator_rate", "*", _gain(rng, 1.3))
    if specialty == "resource":
        return Effect("resource_rate", pick(rng, resources).id, _gain(rng, 1.5))
    if specialty == "efficiency":
        return Effect("generator_cost", "*", round(1.0 - jitter(rng, 0.07, 0.3), 3))
    if specialty == "critical":
        return Effect("crit_chance", "*", round(jitter(rng, 0.05, 0.3), 4), {"mult": round(jitter(rng, 4.0, 0.3), 2)})
    capped = [r for r in resources if r.cap != float("inf")]
    if capped:
        return Effect("resource_cap", pick(rng, capped).id, _gain(rng, 2.5))
    return Effect("global_mult", "", _gain(rng, 1.1))


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------


class InvalidGame(Exception):
    """A generated game violated an invariant the engine relies on."""


def validate_game(game: GameDef) -> None:
    """
    Assert the structural invariants that make a run playable.

    Generative content fails in ways hand-authored content cannot: a resource
    nothing produces, an upgrade priced in a currency you can never earn, a first
    frame with no available action. Every one of those is a soft-locked run, and
    a soft-locked run is indistinguishable from a crash to a player. So the
    generator refuses to return a game that has any of them, and the balance
    harness runs this across hundreds of seeds.
    """
    resource_ids = {r.id for r in game.resources}

    if not game.base_resources:
        raise InvalidGame("no tier-0 resource: nothing can be produced by hand")

    openers = [a for a in game.actions if a.unlock.kind == "none" and not a.cost]
    if not openers:
        raise InvalidGame("no free ungated action: the run cannot start")

    # Every resource needs at least one producer.
    produced = {rid for a in game.actions for rid in a.output}
    produced |= {g.resource for g in game.generators}
    orphans = resource_ids - produced
    if orphans:
        raise InvalidGame(f"resources with no producer: {sorted(orphans)}")

    # Every cost must name a real resource.
    for action in game.actions:
        _check_ids(action.cost, resource_ids, f"action {action.id} cost")
        _check_ids(action.output, resource_ids, f"action {action.id} output")
    for generator in game.generators:
        _check_ids(generator.upkeep, resource_ids, f"generator {generator.id} upkeep")
        if generator.cost_resource not in resource_ids:
            raise InvalidGame(f"generator {generator.id} priced in unknown resource")
        if generator.resource not in resource_ids:
            raise InvalidGame(f"generator {generator.id} produces unknown resource")
        if generator.rate <= 0:
            raise InvalidGame(f"generator {generator.id} produces nothing")
        if generator.cost_growth <= 1.0:
            raise InvalidGame(f"generator {generator.id} has no cost growth: infinite money")
    for upgrade in game.upgrades:
        _check_ids(upgrade.cost, resource_ids, f"upgrade {upgrade.id} cost")
        if not upgrade.effects:
            raise InvalidGame(f"upgrade {upgrade.id} does nothing")

    # Requirement graph must be acyclic and point only at real upgrades.
    upgrade_ids = {u.id for u in game.upgrades}
    for upgrade in game.upgrades:
        for required in upgrade.requires:
            if required not in upgrade_ids:
                raise InvalidGame(f"upgrade {upgrade.id} requires unknown {required}")
            if game.upgrade(required).tier >= upgrade.tier:
                raise InvalidGame(f"upgrade {upgrade.id} requirement is not strictly earlier")

    # Unlock gates must reference things that exist.
    for item in list(game.actions) + list(game.generators) + list(game.upgrades):
        gate = item.unlock
        if gate.kind in {"resource_total", "resource_now"} and gate.target not in resource_ids:
            raise InvalidGame(f"{item.id} gated on unknown resource {gate.target}")
        if gate.kind == "upgrade_owned" and gate.target not in upgrade_ids:
            raise InvalidGame(f"{item.id} gated on unknown upgrade {gate.target}")

    if game.prestige_divisor <= 0:
        raise InvalidGame("prestige divisor must be positive")
    if not game.prestige_upgrades:
        raise InvalidGame("no prestige upgrades: meta-progression is empty")


def _check_ids(bundle: Dict[str, float], known: set, label: str) -> None:
    for rid, amount in bundle.items():
        if rid not in known:
            raise InvalidGame(f"{label} names unknown resource {rid}")
        if amount <= 0:
            raise InvalidGame(f"{label} has non-positive amount for {rid}")
