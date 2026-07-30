"""
Command line entry point.

    python -m incgame serve                  play it
    python -m incgame generate --seed 42     inspect a generated run
    python -m incgame simulate --seed 42     autoplay one run, print metrics
    python -m incgame balance --runs 200     audit many seeds for balance
"""

from __future__ import annotations

import argparse
import json
import sys
from typing import List, Optional, Sequence

from .balance import audit, simulate
from .generator import generate_game, random_seed
from .model import fmt_number


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="incgame", description=__doc__.strip().splitlines()[0])
    sub = parser.add_subparsers(dest="command")

    play = sub.add_parser("serve", help="Run the local game server.")
    play.add_argument("--host", default="127.0.0.1", help="Bind address (default: loopback only).")
    play.add_argument("--port", type=int, default=8000)
    play.add_argument("--seed", type=int, default=None, help="Start with a specific run.")

    show = sub.add_parser("generate", help="Generate a run and describe it.")
    show.add_argument("--seed", type=int, default=None)
    show.add_argument("--json", action="store_true", help="Emit the raw definition.")

    run = sub.add_parser("simulate", help="Autoplay one run and print metrics.")
    run.add_argument("--seed", type=int, default=None)
    run.add_argument("--minutes", type=float, default=30.0)
    run.add_argument("--json", action="store_true")

    check = sub.add_parser("balance", help="Audit many seeds for balance problems.")
    check.add_argument("--runs", type=int, default=100)
    check.add_argument("--start-seed", type=int, default=1)
    check.add_argument("--minutes", type=float, default=20.0)
    check.add_argument("--json", action="store_true")

    return parser


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = build_parser().parse_args(argv)

    if args.command == "serve":
        return _serve(args.host, args.port, args.seed)
    if args.command == "generate":
        return _generate(args.seed, args.json)
    if args.command == "simulate":
        return _simulate(args.seed, args.minutes, args.json)
    if args.command == "balance":
        return _balance(args.runs, args.start_seed, args.minutes, args.json)

    build_parser().print_help()
    return 0


def _serve(host: str, port: int, seed: Optional[int]) -> int:
    from .server import serve

    httpd, url = serve(host=host, port=port, seed=seed)
    print(f"incgame serving on {url}")
    print("Open that in a browser. Ctrl-C to stop.")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nstopping")
    finally:
        httpd.server_close()
    return 0


def _generate(seed: Optional[int], as_json: bool) -> int:
    seed = random_seed() if seed is None else seed
    game = generate_game(seed)

    if as_json:
        json.dump(game.to_dict(), sys.stdout, indent=2)
        print()
        return 0

    print(f"{game.title}   (seed {game.seed})")
    print(game.flavor)
    print()

    print(f"RESOURCES ({len(game.resources)})")
    for resource in game.resources:
        cap = "uncapped" if resource.cap == float("inf") else f"cap {fmt_number(resource.cap)}"
        decay = f", decays {resource.decay * 100:.2f}%/s" if resource.decay else ""
        print(f"  t{resource.tier}  {resource.name:<28} {cap}{decay}")

    print(f"\nACTIONS ({len(game.actions)})")
    for action in game.actions:
        cost = _bundle(game, action.cost) or "free"
        gain = _bundle(game, action.output)
        cooldown = f"  [{action.cooldown:g}s]" if action.cooldown else ""
        print(f"  {action.name:<32} {cost} -> {gain}{cooldown}")

    print(f"\nGENERATORS ({len(game.generators)})")
    for generator in game.generators:
        upkeep = f"  upkeep {_bundle(game, generator.upkeep)}" if generator.upkeep else ""
        print(
            f"  {generator.name:<32} {generator.rate:g}/s {game.resource(generator.resource).name}"
            f"  costs {fmt_number(generator.base_cost)} {game.resource(generator.cost_resource).name}"
            f" x{generator.cost_growth}{upkeep}"
        )

    families: dict = {}
    for upgrade in game.upgrades:
        families.setdefault(upgrade.family, []).append(upgrade)
    print(f"\nUPGRADES ({len(game.upgrades)}) in {len(families)} families")
    for family, members in families.items():
        tiers = sorted({u.tier for u in members})
        print(f"  {family:<20} {len(members):>3} upgrades, tiers {tiers}")

    print(f"\nMECHANICS ({len(game.mechanics)})")
    for mechanic in game.mechanics:
        print(f"  [{mechanic.kind}] {mechanic.name}")
        print(f"      {mechanic.description}")

    print(f"\nPRESTIGE: {game.prestige_name}  (divisor {fmt_number(game.prestige_divisor)})")
    for prestige in game.prestige_upgrades:
        levels = f"x{prestige.max_level}" if prestige.max_level > 1 else "one-off"
        print(f"  {prestige.name:<32} {fmt_number(prestige.base_cost):>8}  {levels}")
    return 0


def _simulate(seed: Optional[int], minutes: float, as_json: bool) -> int:
    seed = random_seed() if seed is None else seed
    game = generate_game(seed)
    metrics = simulate(game, seconds=minutes * 60.0)

    if as_json:
        json.dump(metrics.to_dict(), sys.stdout, indent=2)
        print()
        return 1 if metrics.problems else 0

    print(f"{metrics.title}   (seed {metrics.seed})")
    print(f"  simulated            {metrics.seconds / 60:.0f} minutes")
    print(f"  resources / max tier {metrics.resources} / {metrics.max_tier}")
    print(f"  mechanics            {', '.join(metrics.mechanics) or 'none'}")
    print(f"  actions taken        {metrics.actions_taken}")
    print(f"  upgrades bought      {metrics.upgrades_bought} (holding {metrics.upgrades_held} of {metrics.upgrades})")
    print(f"  generators bought    {metrics.generators_bought} (holding {metrics.generators_held})")
    print(f"  first upgrade at     {_seconds(metrics.first_upgrade_at)}")
    print(f"  first generator at   {_seconds(metrics.first_generator_at)}")
    print(f"  prestige ready at    {_seconds(metrics.first_prestige_at)}")
    print(f"  prestige points      {fmt_number(metrics.prestige_points)}")
    print(f"  ascensions           {metrics.ascensions}")
    print(f"  longest stall        {metrics.stalled_for:.0f}s")
    if metrics.problems:
        print("\n  PROBLEMS")
        for problem in metrics.problems:
            print(f"    - {problem}")
        return 1
    print("\n  no problems detected")
    return 0


def _balance(runs: int, start_seed: int, minutes: float, as_json: bool) -> int:
    seeds: List[int] = list(range(start_seed, start_seed + runs))
    report = audit(seeds, seconds=minutes * 60.0)

    if as_json:
        json.dump(report, sys.stdout, indent=2)
        print()
        return 0 if not report["failures"] else 1

    print(f"audited {report['seeds']} seeds at {minutes:g} simulated minutes each")
    print(f"  healthy: {report['healthy']}/{report['seeds']}")
    print("\n  medians")
    for key, value in report["medians"].items():
        print(f"    {key:<20} {value}")
    print("\n  mechanic frequency")
    for kind, count in report["mechanic_frequency"].items():
        print(f"    {kind:<20} {count}")
    if report["failures"]:
        print(f"\n  {len(report['failures'])} seeds with problems")
        for failure in report["failures"][:20]:
            print(f"    seed {failure['seed']}: {'; '.join(failure['problems'])}")
        if len(report["failures"]) > 20:
            print(f"    ... and {len(report['failures']) - 20} more")
        return 1
    print("\n  all seeds healthy")
    return 0


def _bundle(game, bundle: dict) -> str:
    if not bundle:
        return ""
    return ", ".join(f"{fmt_number(v)} {game.resource(k).name}" for k, v in bundle.items())


def _seconds(value: Optional[float]) -> str:
    return "never" if value is None else f"{value:.0f}s"


if __name__ == "__main__":
    raise SystemExit(main())
