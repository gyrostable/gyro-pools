from decimal import Decimal
from typing import List, Tuple, Union, overload

from tests.support.quantized_decimal import DecimalLike, QuantizedDecimal

from hypothesis import strategies as st

def scalar_to_decimal(x: DecimalLike):
    assert isinstance(x, (Decimal, int, str, QuantizedDecimal))
    if isinstance(x, QuantizedDecimal):
        return x
    return QuantizedDecimal(x)


@overload
def to_decimal(
    x: Union[List[DecimalLike], Tuple[DecimalLike, ...]]
) -> List[QuantizedDecimal]:
    ...


@overload
def to_decimal(x: DecimalLike) -> QuantizedDecimal:
    ...


def to_decimal(x: Union[List[DecimalLike], Tuple[DecimalLike], DecimalLike]):
    if isinstance(x, (list, tuple)):
        return [scalar_to_decimal(v) for v in x]
    return scalar_to_decimal(x)


def scale_scalar(x: DecimalLike, decimals: int = 18) -> QuantizedDecimal:
    return (to_decimal(x) * 10 ** decimals).floor()


def unscale_scalar(x: DecimalLike, decimals: int = 18) -> QuantizedDecimal:
    return to_decimal(x) / 10**decimals

@overload
def scale(
    x: Union[List[DecimalLike], Tuple[DecimalLike, ...]]
) -> List[QuantizedDecimal]:
    ...


@overload
def scale(x: DecimalLike) -> QuantizedDecimal:
    ...


def scale(x, decimals=18):
    if isinstance(x, (list, tuple)):
        return [scale_scalar(v, decimals) for v in x]
    return scale_scalar(x, decimals)

def unscale(x, decimals=18):
    if isinstance(x, (list, tuple)):
        return [unscale_scalar(v, decimals) for v in x]
    return unscale_scalar(x, decimals)

def qdecimals(*args, **kwargs) -> st.SearchStrategy[QuantizedDecimal]:
    return st.decimals(*args, **kwargs).map(QuantizedDecimal)
