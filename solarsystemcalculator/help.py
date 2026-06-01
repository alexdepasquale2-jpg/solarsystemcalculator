from __future__ import annotations

import argparse
from typing import Optional, Sequence


COMMANDS = [
    {
        "name": "Distance CLI",
        "command": "python -m solarsystemcalculator earth mars --unit au --date 2024-06-20T20:51:00Z",
        "purpose": "Calculate distance between two bodies at a point in time.",
    },
    {
        "name": "Desktop GUI",
        "command": "python -m solarsystemcalculator.gui",
        "purpose": "Open the ergonomic calculator and training control panel.",
    },
    {
        "name": "Generate Observations",
        "command": "python generate_observations.py --bodies mars earth --count 128 --seed 42",
        "purpose": "Append random JPL ephemeris positions to observations.csv.",
    },
    {
        "name": "Train Residual Model",
        "command": "python self_improve.py observations.csv --model gaussian_process",
        "purpose": "Train and validate residual corrections from observation data.",
    },
    {
        "name": "Package Install",
        "command": "pip install .[ml,ephemeris]",
        "purpose": "Install the package with ML and JPL ephemeris support.",
    },
]


def command_text() -> str:
    lines = [
        "Solar System Calculator Commands",
        "",
        "Core workflow:",
        "  1. Generate observation data from a trusted ephemeris.",
        "  2. Train a residual model against those observations.",
        "  3. Use the package or GUI for calculations and inspection.",
        "",
        "Commands:",
    ]

    for item in COMMANDS:
        lines.extend(
            [
                f"",
                f"{item['name']}",
                f"  {item['command']}",
                f"  {item['purpose']}",
            ]
        )

    lines.extend(
        [
            "",
            "Observation CSV columns:",
            "  body,datetime,x_au,y_au,z_au",
            "",
            "Useful help commands:",
            "  python -m solarsystemcalculator --help",
            "  python -m solarsystemcalculator commands",
            "  python generate_observations.py --help",
            "  python self_improve.py --help",
        ]
    )
    return "\n".join(lines)


def build_parser() -> argparse.ArgumentParser:
    return argparse.ArgumentParser(
        description="List Solar System Calculator commands and workflows."
    )


def main(argv: Optional[Sequence[str]] = None) -> int:
    build_parser().parse_args(argv)
    print(command_text())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
