"""Shared formatting for physical cursor values and exported measurements."""
import math


def scientific(value):
    """Format finite numbers with ten significant digits and an explicit e exponent."""
    value = float(value)
    if not math.isfinite(value): return str(value)
    mantissa, exponent = f'{value:.9e}'.split('e')
    return f'{mantissa.rstrip("0").rstrip(".")}e{int(exponent)}'
