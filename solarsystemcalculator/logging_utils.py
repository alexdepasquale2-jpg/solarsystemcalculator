"""
Logging and error handling utilities for the solar system calculator.
"""

import logging
import sys
from typing import Optional

# Logger instance
_logger: Optional[logging.Logger] = None


def get_logger(name: str = "solarsystemcalculator", verbose: bool = False) -> logging.Logger:
    """
    Get or create a logger for the package.
    
    Parameters:
        name: Logger name
        verbose: Enable debug logging
    
    Returns:
        Configured logger instance
    """
    global _logger
    
    if _logger is not None:
        return _logger
    
    _logger = logging.getLogger(name)
    level = logging.DEBUG if verbose else logging.INFO
    _logger.setLevel(level)
    
    # Console handler
    handler = logging.StreamHandler(sys.stderr)
    handler.setLevel(level)
    
    formatter = logging.Formatter(
        "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )
    handler.setFormatter(formatter)
    
    _logger.addHandler(handler)
    return _logger


class CalculationError(Exception):
    """Raised when a calculation cannot be completed."""
    pass


class InvalidBodyError(CalculationError):
    """Raised when an invalid body name is provided."""
    pass


class ValidationError(CalculationError):
    """Raised when input validation fails."""
    pass


def validate_body_name(body: str) -> str:
    """
    Validate and normalize body name.
    
    Parameters:
        body: Body name (case-insensitive)
    
    Returns:
        Normalized body name
    
    Raises:
        InvalidBodyError: If body name is invalid
    """
    from .planets import PLANET_ALIASES, BODY_PROPERTIES
    
    normalized = body.lower().strip()
    
    if normalized in BODY_PROPERTIES:
        return normalized
    
    if normalized in PLANET_ALIASES:
        return PLANET_ALIASES[normalized]
    
    valid_bodies = ", ".join(sorted(BODY_PROPERTIES.keys()))
    raise InvalidBodyError(
        f"Unknown body: {body!r}. Valid bodies: {valid_bodies}"
    )


def validate_datetime(dt, allow_none: bool = True):
    """
    Validate datetime object.
    
    Parameters:
        dt: Datetime to validate
        allow_none: Whether None is acceptable
    
    Returns:
        Validated datetime
    
    Raises:
        ValidationError: If datetime is invalid
    """
    from datetime import datetime, timezone
    
    if dt is None:
        if allow_none:
            return datetime.now(timezone.utc)
        raise ValidationError("Datetime cannot be None")
    
    if not isinstance(dt, datetime):
        raise ValidationError(f"Expected datetime, got {type(dt).__name__}")
    
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    
    return dt.astimezone(timezone.utc)
