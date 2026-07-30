"""
Seeded randomness helpers.

Every generated value in the game flows through one of these functions, and all
of them take an explicit `random.Random`. There is no module-level RNG and no
use of the global `random` state anywhere in the package -- that is what makes a
seed reproducible.
"""

from __future__ import annotations

import colorsys
import random
from typing import Dict, List, Sequence, TypeVar

T = TypeVar("T")


class Namer:
    """
    Hands out names from word pools without repeating itself.

    A run that calls two things "Gilded Ember" reads as a bug, so the namer
    tracks every phrase it has produced and re-rolls on collision. It gives up
    after a bounded number of attempts and appends a roman numeral rather than
    looping forever on a small pool.
    """

    ROMAN = ["", " II", " III", " IV", " V", " VI", " VII", " VIII", " IX", " X"]

    def __init__(self, rng: random.Random):
        self.rng = rng
        self._used: set[str] = set()

    def unique(self, *pools: Sequence[str], attempts: int = 24) -> str:
        """Compose one word from each pool, avoiding names already handed out."""
        candidate = ""
        for _ in range(attempts):
            candidate = " ".join(self.rng.choice(pool) for pool in pools)
            if candidate not in self._used:
                self._used.add(candidate)
                return candidate
        # Pool exhausted: disambiguate deterministically.
        for suffix in self.ROMAN[1:]:
            decorated = candidate + suffix
            if decorated not in self._used:
                self._used.add(decorated)
                return decorated
        self._used.add(candidate)
        return candidate

    def reserve(self, name: str) -> None:
        self._used.add(name)


def pick(rng: random.Random, seq: Sequence[T]) -> T:
    return rng.choice(seq)


def pick_n(rng: random.Random, seq: Sequence[T], n: int) -> List[T]:
    """Sample without replacement, clamped to the length of `seq`."""
    n = max(0, min(n, len(seq)))
    return rng.sample(list(seq), n)


def weighted(rng: random.Random, options: Dict[T, float]) -> T:
    """Pick one key from {option: weight}. Weights need not sum to 1."""
    if not options:
        raise ValueError("weighted() needs at least one option")
    total = sum(max(0.0, w) for w in options.values())
    if total <= 0:
        return next(iter(options))
    roll = rng.random() * total
    upto = 0.0
    for option, weight in options.items():
        upto += max(0.0, weight)
        if roll <= upto:
            return option
    return next(reversed(list(options)))


def jitter(rng: random.Random, value: float, spread: float = 0.25) -> float:
    """Multiply `value` by a factor in [1-spread, 1+spread]."""
    return value * (1.0 + rng.uniform(-spread, spread))


def round_nice(value: float) -> float:
    """
    Round to something a player would read as a deliberate number.

    Costs like 47.3182 look procedurally generated in the worst way. This snaps
    to 1/2/2.5/5 significant leading digits at the right magnitude.
    """
    if value <= 0:
        return 0.0
    magnitude = 10 ** int(_floor_log10(value))
    scaled = value / magnitude
    for step in (1.0, 1.5, 2.0, 2.5, 3.0, 4.0, 5.0, 7.5, 10.0):
        if scaled <= step:
            return step * magnitude
    return 10.0 * magnitude


def _floor_log10(value: float) -> int:
    exponent = 0
    while value >= 10.0:
        value /= 10.0
        exponent += 1
    while value < 1.0:
        value *= 10.0
        exponent -= 1
    return exponent


def hue_palette(rng: random.Random, count: int) -> List[str]:
    """
    Generate `count` visually distinct hex colours.

    Hues are spread evenly around the wheel from a random offset so no two
    resources in a run are hard to tell apart, then saturation and lightness get
    small per-colour jitter so the palette does not look mechanical. Lightness
    stays in the upper half of the range because the UI is dark-themed.
    """
    offset = rng.random()
    colours: List[str] = []
    for index in range(count):
        hue = (offset + index / max(1, count) + rng.uniform(-0.03, 0.03)) % 1.0
        saturation = rng.uniform(0.55, 0.85)
        lightness = rng.uniform(0.58, 0.72)
        r, g, b = colorsys.hls_to_rgb(hue, lightness, saturation)
        colours.append("#%02x%02x%02x" % (int(r * 255), int(g * 255), int(b * 255)))
    return colours


def theme(rng: random.Random) -> Dict[str, str]:
    """Pick the run's background/accent theme, keyed off one base hue."""
    base = rng.random()
    accent_r, accent_g, accent_b = colorsys.hls_to_rgb(base, 0.66, 0.72)
    dim_r, dim_g, dim_b = colorsys.hls_to_rgb((base + 0.5) % 1.0, 0.62, 0.45)
    return {
        "hue": f"{base * 360:.1f}",
        "accent": "#%02x%02x%02x" % (int(accent_r * 255), int(accent_g * 255), int(accent_b * 255)),
        "secondary": "#%02x%02x%02x" % (int(dim_r * 255), int(dim_g * 255), int(dim_b * 255)),
    }


def slug(text: str) -> str:
    """Turn a display name into a stable id."""
    out = []
    for char in text.lower():
        if char.isalnum():
            out.append(char)
        elif out and out[-1] != "_":
            out.append("_")
    return "".join(out).strip("_")
