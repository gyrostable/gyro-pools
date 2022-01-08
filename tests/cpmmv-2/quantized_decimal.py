# Created by danhper
# Minor changes by sschuldenzucker
#
# This is different from Decimal in that (say) if DECIMAL_PRECISION=3, then QuantizedDecimal('0.0005') == 0. This is
# the behavior we'd expect from a fixed-point implementation.

from __future__ import annotations

import math
import decimal
from functools import total_ordering
from typing import Any, Optional, Union

DECIMAL_PRECISION = 18
# v Total number of decimal places. This matches uint256, to the degree possible (max uint256 ≈ 1.16e+77).
MAX_PREC_VALUE = 78

QUANTIZED_EXP = decimal.Decimal(1) / decimal.Decimal(10 ** DECIMAL_PRECISION)

# 1.000000... multiplier to increase the precision to the required level by multiplying
DECIMAL_MULT = QUANTIZED_EXP * decimal.Decimal(10 ** DECIMAL_PRECISION)

# Workaround a brownie issue:
# - In Brownie, prec is already set to 78 and you can't set it. (through vyper for some reason)
# - Outside brownie, prec is lower than that and you should set it.
if decimal.getcontext().prec != MAX_PREC_VALUE:
    decimal.getcontext().prec = MAX_PREC_VALUE


@total_ordering
class QuantizedDecimal:
    """Wrapper of `decimal.Decimal` with quantized semantics
    meaning that all operations will be quantized down to the `DECIMAL_PRECISION`
    set in `constants`
    """

    def __init__(self, value="0", context=None):
        if isinstance(value, QuantizedDecimal):
            value = value * DECIMAL_MULT
            self._value = value._value
        elif isinstance(value, decimal.Decimal):
            value = value * DECIMAL_MULT
            self._value = self._quantize(value)
        else:
            rounding = decimal.ROUND_DOWN
            if isinstance(value, float):
                rounding = decimal.ROUND_HALF_DOWN
            high_prec_value = decimal.Decimal(value, context=context) * DECIMAL_MULT
            self._value = self._quantize(high_prec_value, rounding=rounding)

    @property
    def raw(self):
        return self._value

    @staticmethod
    def _quantize(
        value: decimal.Decimal, rounding=decimal.ROUND_DOWN
    ) -> decimal.Decimal:
        return value.quantize(QUANTIZED_EXP, rounding=rounding)

    def quantize_to_lower_precision(self, rounding=decimal.ROUND_DOWN):
        return self._value.quantize(QUANTIZED_EXP, rounding=rounding)

    def __add__(self, other: DecimalLike):
        return QuantizedDecimal(self._value + self._get_value(other))

    def __radd__(self, other: DecimalLike):
        return QuantizedDecimal(self._value + self._get_value(other))

    def __sub__(self, other: DecimalLike):
        return QuantizedDecimal(self._value - self._get_value(other))

    def __rsub__(self, other: DecimalLike):
        return QuantizedDecimal(self._get_value(other) - self._value)

    def __mul__(self, other: DecimalLike):
        return QuantizedDecimal(self._value * self._get_value(other))

    def __rmul__(self, other: DecimalLike):
        return QuantizedDecimal(self._value * self._get_value(other))

    def __truediv__(self, other: DecimalLike):
        return QuantizedDecimal(self._value / self._get_value(other))

    def __rtruediv__(self, other: DecimalLike):
        return QuantizedDecimal(self._get_value(other) / self._value)

    def __floordiv__(self, other: DecimalLike):
        return QuantizedDecimal(self._value // self._get_value(other))

    def __rfloordiv__(self, other: DecimalLike):
        return QuantizedDecimal(self._get_value(other) // self._value)

    def __pow__(self, other: DecimalLike):
        return QuantizedDecimal(self._value ** self._get_value(other))

    def __eq__(self, other: Any):
        if isinstance(other, QuantizedDecimal):
            return (
                self.quantize_to_lower_precision()
                == other.quantize_to_lower_precision()
            )
        return self.quantize_to_lower_precision() == other

    def __ne__(self, other: Any):
        if isinstance(other, QuantizedDecimal):
            return (
                self.quantize_to_lower_precision()
                != other.quantize_to_lower_precision()
            )
        return self.quantize_to_lower_precision() != other

    def __lt__(self, other: DecimalLike):
        if isinstance(other, QuantizedDecimal):
            return (
                self.quantize_to_lower_precision() < other.quantize_to_lower_precision()
            )
        return self.quantize_to_lower_precision() < other

    def __hash__(self):
        return hash(self._value)

    def __neg__(self):
        return QuantizedDecimal(-self._value)

    def __abs__(self):
        return QuantizedDecimal(abs(self._value))

    def __int__(self):
        return int(self._value)

    def __float__(self):
        return float(self._value)

    def is_zero(self):
        return self == 0

    def sqrt(self):
        """For consistency with Decimal"""
        return self ** QuantizedDecimal("0.5")

    def floor(self):
        return QuantizedDecimal(math.floor(self._value))

    @classmethod
    def from_float(cls, value: float) -> QuantizedDecimal:
        return cls(value)

    @staticmethod
    def _get_value(value: DecimalLike) -> decimal.Decimal:
        if isinstance(value, QuantizedDecimal):
            return value._value  # pylint: disable=protected-access
        elif isinstance(value, int):
            return decimal.Decimal(value)
        return value

    def __repr__(self):
        return repr(self._value)

    def __str__(self):
        return str(self._value)


DecimalLike = Union[int, decimal.Decimal, QuantizedDecimal]


def quantize_to_lower_precision(value: Optional[QuantizedDecimal]):
    if value is not None:
        return value.quantize_to_lower_precision()
    else:
        return value
