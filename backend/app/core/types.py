"""
PROVENIQ Ops - Canonical Money & Quantity Types
================================================

RULE: No floats allowed for money or quantities.

Money:  int micros (1 USD = 1_000_000 micros)
        - Prevents rounding errors
        - Safe for arithmetic
        - JSON-serializable as integer

Quantity: Decimal (for partial units like 2.5 lbs)
        - Stored as NUMERIC in DB
        - Serialized as string in JSON
        - Never use float

This module is the SINGLE SOURCE OF TRUTH for numeric types in Ops.
All schemas and models MUST import from here.
"""

from decimal import Decimal, ROUND_HALF_UP
from typing import Annotated, Any

from pydantic import BeforeValidator, PlainSerializer, WithJsonSchema


# =============================================================================
# MONEY (Integer Micros)
# =============================================================================
# 1 USD = 1,000,000 micros
# $19.99 = 19_990_000 micros
# This eliminates ALL floating point issues for money

MICROS_PER_UNIT = 1_000_000


def _validate_money_micros(v: Any) -> int:
    """
    Validate and convert to money micros.
    
    Accepts:
        - int: Already in micros
        - str: Parse as decimal, convert to micros
        - Decimal: Convert to micros
        - float: REJECTED (raises ValueError)
    """
    if isinstance(v, float):
        raise ValueError(
            "Float not allowed for money. Use int micros or Decimal string. "
            f"Got: {v}"
        )
    
    if isinstance(v, int):
        return v
    
    if isinstance(v, str):
        # Parse string as decimal dollars, convert to micros
        try:
            dec = Decimal(v)
            return int(dec * MICROS_PER_UNIT)
        except Exception:
            raise ValueError(f"Invalid money string: {v}")
    
    if isinstance(v, Decimal):
        return int(v * MICROS_PER_UNIT)
    
    raise ValueError(f"Invalid money type: {type(v)}")


def _serialize_money_micros(v: int) -> int:
    """Serialize money as integer micros."""
    return v


# Money type: stored and transferred as integer micros
MoneyMicros = Annotated[
    int,
    BeforeValidator(_validate_money_micros),
    PlainSerializer(_serialize_money_micros),
    WithJsonSchema({"type": "integer", "description": "Money in micros (1 USD = 1,000,000)"}),
]


class Money:
    """
    Money utilities for working with micros.
    
    Usage:
        price_micros = Money.from_dollars(19.99)  # -> 19_990_000
        price_str = Money.to_dollars_str(19_990_000)  # -> "19.99"
        price_dec = Money.to_decimal(19_990_000)  # -> Decimal("19.99")
    """
    
    @staticmethod
    def from_dollars(dollars: Decimal | str) -> int:
        """Convert dollars to micros. No floats allowed."""
        if isinstance(dollars, float):
            raise ValueError("Float not allowed. Use Decimal or string.")
        dec = Decimal(str(dollars))
        return int(dec * MICROS_PER_UNIT)
    
    @staticmethod
    def to_decimal(micros: int) -> Decimal:
        """Convert micros to Decimal dollars."""
        return Decimal(micros) / MICROS_PER_UNIT
    
    @staticmethod
    def to_dollars_str(micros: int, places: int = 2) -> str:
        """Convert micros to formatted dollar string."""
        dec = Decimal(micros) / MICROS_PER_UNIT
        quantized = dec.quantize(Decimal(10) ** -places, rounding=ROUND_HALF_UP)
        return str(quantized)
    
    @staticmethod
    def add(a: int, b: int) -> int:
        """Add two money values (micros)."""
        return a + b
    
    @staticmethod
    def multiply(micros: int, factor: Decimal | str | int) -> int:
        """Multiply money by a factor. Factor can be Decimal/str/int, NOT float."""
        if isinstance(factor, float):
            raise ValueError("Float not allowed. Use Decimal or string.")
        dec_factor = Decimal(str(factor))
        result = Decimal(micros) * dec_factor
        return int(result.quantize(Decimal("1"), rounding=ROUND_HALF_UP))


# =============================================================================
# QUANTITY (Decimal)
# =============================================================================
# For partial units like 2.5 lbs, 0.75 gallons
# Stored as NUMERIC in DB, serialized as string in JSON

def _validate_quantity(v: Any) -> Decimal:
    """
    Validate and convert to Decimal quantity.
    
    Accepts:
        - Decimal: Pass through
        - str: Parse as Decimal
        - int: Convert to Decimal
        - float: REJECTED (raises ValueError)
    """
    if isinstance(v, float):
        raise ValueError(
            "Float not allowed for quantity. Use Decimal or string. "
            f"Got: {v}"
        )
    
    if isinstance(v, Decimal):
        return v
    
    if isinstance(v, (str, int)):
        try:
            return Decimal(str(v))
        except Exception:
            raise ValueError(f"Invalid quantity: {v}")
    
    raise ValueError(f"Invalid quantity type: {type(v)}")


def _serialize_quantity(v: Decimal) -> str:
    """Serialize quantity as string (prevents JSON float issues)."""
    return str(v)


# Quantity type: Decimal, serialized as string
Quantity = Annotated[
    Decimal,
    BeforeValidator(_validate_quantity),
    PlainSerializer(_serialize_quantity),
    WithJsonSchema({"type": "string", "description": "Decimal quantity as string"}),
]


# =============================================================================
# INTEGER QUANTITY (Whole Units)
# =============================================================================
# For countable items that can't be fractional

def _validate_int_quantity(v: Any) -> int:
    """Validate integer quantity (whole units only)."""
    if isinstance(v, float):
        raise ValueError(f"Float not allowed for integer quantity. Got: {v}")
    
    if isinstance(v, int):
        return v
    
    if isinstance(v, str):
        try:
            return int(v)
        except Exception:
            raise ValueError(f"Invalid integer quantity: {v}")
    
    if isinstance(v, Decimal):
        if v % 1 != 0:
            raise ValueError(f"Quantity must be whole number, got: {v}")
        return int(v)
    
    raise ValueError(f"Invalid quantity type: {type(v)}")


IntQuantity = Annotated[
    int,
    BeforeValidator(_validate_int_quantity),
    WithJsonSchema({"type": "integer", "description": "Whole unit quantity"}),
]


# =============================================================================
# PERCENTAGE / RATE (Decimal, 0-1 or 0-100)
# =============================================================================

def _validate_rate(v: Any) -> Decimal:
    """Validate rate/percentage as Decimal 0-1."""
    if isinstance(v, float):
        raise ValueError(f"Float not allowed for rate. Use Decimal or string. Got: {v}")
    
    dec = Decimal(str(v)) if not isinstance(v, Decimal) else v
    
    if dec < 0 or dec > 1:
        raise ValueError(f"Rate must be 0-1, got: {dec}")
    
    return dec


Rate = Annotated[
    Decimal,
    BeforeValidator(_validate_rate),
    PlainSerializer(_serialize_quantity),
    WithJsonSchema({"type": "string", "description": "Rate as decimal 0-1"}),
]


def _validate_percentage(v: Any) -> Decimal:
    """Validate percentage as Decimal 0-100."""
    if isinstance(v, float):
        raise ValueError(f"Float not allowed for percentage. Got: {v}")
    
    dec = Decimal(str(v)) if not isinstance(v, Decimal) else v
    
    if dec < 0 or dec > 100:
        raise ValueError(f"Percentage must be 0-100, got: {dec}")
    
    return dec


Percentage = Annotated[
    Decimal,
    BeforeValidator(_validate_percentage),
    PlainSerializer(_serialize_quantity),
    WithJsonSchema({"type": "string", "description": "Percentage 0-100"}),
]


# =============================================================================
# CONVENIENCE EXPORTS
# =============================================================================

__all__ = [
    # Money
    "MoneyMicros",
    "Money",
    "MICROS_PER_UNIT",
    
    # Quantity
    "Quantity",
    "IntQuantity",
    
    # Rates
    "Rate",
    "Percentage",
]
