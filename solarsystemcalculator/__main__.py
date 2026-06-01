import argparse
import sys
from datetime import datetime, timezone
from typing import Optional, Sequence

from . import SolarSystemCalculator, format_distance
from .help import command_text
from .logging_utils import get_logger, CalculationError, validate_body_name


def _parse_datetime(value: str) -> datetime:
    """Parse an ISO datetime and assume UTC for naive values."""
    try:
        dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if dt.tzinfo is None:
            return dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)
    except ValueError as e:
        raise argparse.ArgumentTypeError(f"Invalid datetime format: {value!r}. Use ISO format (e.g., 2024-06-20T20:51:00Z)") from e


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Calculate approximate distances between solar system bodies. "
            "Use `python -m solarsystemcalculator commands` to list all workflows."
        )
    )
    parser.add_argument("body1", help="First body, such as earth, mars, or sun.")
    parser.add_argument("body2", help="Second body, such as mars, jupiter, or sun.")
    parser.add_argument(
        "--date",
        type=_parse_datetime,
        help="ISO datetime. Naive values are treated as UTC.",
    )
    parser.add_argument(
        "--unit",
        default="km",
        choices=["km", "au", "m", "miles", "light_seconds"],
        help="Output unit.",
    )
    parser.add_argument(
        "--precision",
        default="high",
        choices=["high", "max"],
        help="Numeric precision mode.",
    )
    parser.add_argument(
        "--ephemeris",
        default=None,
        help="Optional Skyfield ephemeris name or file path for higher-accuracy positions.",
    )
    parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="Enable verbose logging for debugging.",
    )
    return parser


def main(argv: Optional[Sequence[str]] = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    
    try:
        if argv and argv[0] in {"commands", "help-all"}:
            print(command_text())
            return 0

        args = build_parser().parse_args(argv)
        logger = get_logger(verbose=args.verbose)
        
        # Validate body names
        try:
            body1_normalized = validate_body_name(args.body1)
            body2_normalized = validate_body_name(args.body2)
        except CalculationError as e:
            print(f"Error: {e}", file=sys.stderr)
            return 1
        
        logger.debug(f"Calculating distance between {body1_normalized} and {body2_normalized}")
        
        calc = SolarSystemCalculator(precision=args.precision, ephemeris=args.ephemeris)
        value = calc.distance(body1_normalized, body2_normalized, dt=args.date, unit=args.unit)

        if args.unit == "km":
            print(format_distance(value))
        else:
            print(f"{value:.12g} {args.unit}")

        return 0
    
    except KeyboardInterrupt:
        print("\nInterrupted by user", file=sys.stderr)
        return 130
    except Exception as e:
        print(f"Fatal error: {e}", file=sys.stderr)
        if "--verbose" in (argv or []):
            import traceback
            traceback.print_exc()
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
