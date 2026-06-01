import argparse
import csv
import random
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Iterable, List, Optional, Sequence, Set, Tuple

from solarsystemcalculator import SolarSystemCalculator


BODIES = ["mercury", "venus", "earth", "mars", "jupiter", "saturn", "uranus", "neptune"]
CSV_COLUMNS = ["body", "datetime", "x_au", "y_au", "z_au"]


def parse_datetime(value: str) -> datetime:
    dt = datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def format_datetime(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def existing_keys(path: Path) -> Set[Tuple[str, str]]:
    if not path.exists():
        return set()

    with path.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        return {
            ((row.get("body") or "").strip().lower(), (row.get("datetime") or "").strip())
            for row in reader
        }


def random_datetimes(start: datetime, end: datetime, count: int, rng: random.Random) -> List[datetime]:
    if end <= start:
        raise ValueError("--end must be after --start")

    seconds = int((end - start).total_seconds())
    return [
        start + timedelta(seconds=rng.randint(0, seconds))
        for _ in range(count)
    ]


def generate_rows(
    calc: SolarSystemCalculator,
    bodies: Sequence[str],
    dates: Iterable[datetime],
) -> List[dict]:
    rows = []
    for dt in dates:
        for body in bodies:
            x, y, z = calc.position(body, dt=dt, unit="au")
            rows.append(
                {
                    "body": body,
                    "datetime": format_datetime(dt),
                    "x_au": f"{x:.16e}",
                    "y_au": f"{y:.16e}",
                    "z_au": f"{z:.16e}",
                }
            )
    return rows


def write_rows(path: Path, rows: Sequence[dict], replace: bool = False) -> int:
    path.parent.mkdir(parents=True, exist_ok=True)
    mode = "w" if replace or not path.exists() else "a"
    write_header = mode == "w" or path.stat().st_size == 0

    keys = set() if replace else existing_keys(path)
    filtered = []
    for row in rows:
        key = (row["body"], row["datetime"])
        if key not in keys:
            filtered.append(row)
            keys.add(key)

    with path.open(mode, newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=CSV_COLUMNS, lineterminator="\n")
        if write_header:
            writer.writeheader()
        writer.writerows(filtered)

    return len(filtered)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Append random high-accuracy JPL ephemeris observations to observations.csv "
            "for residual-model training."
        )
    )
    parser.add_argument("--output", type=Path, default=Path("observations.csv"), help="CSV file to append.")
    parser.add_argument(
        "--bodies",
        nargs="+",
        default=["mars"],
        choices=BODIES,
        help="Bodies to sample. Use multiple names for multi-body training data.",
    )
    parser.add_argument("--count", type=int, default=64, help="Number of random timestamps to generate.")
    parser.add_argument("--start", default="1900-01-01T00:00:00Z", help="Inclusive UTC start datetime.")
    parser.add_argument("--end", default="2050-01-01T00:00:00Z", help="Inclusive UTC end datetime.")
    parser.add_argument("--seed", type=int, default=None, help="Random seed for reproducible datasets.")
    parser.add_argument(
        "--ephemeris",
        default="de421.bsp",
        help="Skyfield/JPL ephemeris file or name. Local de421.bsp is used by default.",
    )
    parser.add_argument("--replace", action="store_true", help="Rewrite the output file instead of appending.")
    parser.add_argument("--dry-run", action="store_true", help="Print generated rows without writing.")
    return parser


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = build_parser().parse_args(argv)
    if args.count <= 0:
        raise ValueError("--count must be positive")

    rng = random.Random(args.seed)
    start = parse_datetime(args.start)
    end = parse_datetime(args.end)
    dates = sorted(random_datetimes(start, end, args.count, rng))
    calc = SolarSystemCalculator(precision="high", ephemeris=args.ephemeris)
    rows = generate_rows(calc, args.bodies, dates)

    if args.dry_run:
        writer = csv.DictWriter(__import__("sys").stdout, fieldnames=CSV_COLUMNS, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows[: min(len(rows), 25)])
        if len(rows) > 25:
            print(f"... {len(rows) - 25} more rows")
        return 0

    written = write_rows(args.output, rows, replace=args.replace)
    print(f"generated: {len(rows)} rows")
    print(f"written:   {written} new rows")
    print(f"output:    {args.output}")
    print(f"source:    {args.ephemeris}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
