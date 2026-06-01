"""
Solar System Distance Calculator

Formula-based orbital mechanics for calculating approximate distances
between major solar-system bodies.
"""

from .calculator import OrbitState, SolarSystemCalculator, distance
from .planets import (
    BodyProperties,
    OrbitalElements,
    PLANET_ALIASES,
    PLANETARY_ELEMENTS,
    BODY_PROPERTIES,
    get_body_properties,
    get_planet,
)
from .utils import find_conjunction, format_distance
from .logging_utils import (
    get_logger,
    CalculationError,
    InvalidBodyError,
    ValidationError,
    validate_body_name,
)

__version__ = "1.0.0"

__all__ = [
    "SolarSystemCalculator",
    "OrbitState",
    "distance",
    "BodyProperties",
    "OrbitalElements",
    "PLANETARY_ELEMENTS",
    "BODY_PROPERTIES",
    "PLANET_ALIASES",
    "get_body_properties",
    "get_planet",
    "format_distance",
    "find_conjunction",
    "get_logger",
    "CalculationError",
    "InvalidBodyError",
    "ValidationError",
    "validate_body_name",
    "__version__",
]
