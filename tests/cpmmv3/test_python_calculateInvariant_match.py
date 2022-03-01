from pprint import pprint
from typing import Iterable

import pytest
from hypothesis import given, settings

from tests.support.util_common import gen_balances, BasicPoolParameters
from tests.support.utils import to_decimal, qdecimals

from tests.support.quantized_decimal import QuantizedDecimal as D
import tests.cpmmv3.v3_math_implementation as mimpl

ROOT_ALPHA_MAX = "0.99996666555"
ROOT_ALPHA_MIN = "0.2"
MIN_BAL_RATIO = to_decimal("1e-5")
MIN_FEE = to_decimal("0.0001")

bpool_params = BasicPoolParameters(
    D(1)/D(ROOT_ALPHA_MAX)**3 - D(ROOT_ALPHA_MAX)**3,
    D('0.3'), D('0.3'),
    MIN_BAL_RATIO,
    MIN_FEE,
    max_balances=100_000_000_000
)

@settings(max_examples=10_000)
@given(
    balances=gen_balances(3, bpool_params),
    root3Alpha=qdecimals(ROOT_ALPHA_MIN, ROOT_ALPHA_MAX)
)
def test_calculateInvariant_match(balances: Iterable[D], root3Alpha: D):
    invariant_fixedpoint = mimpl.calculateInvariant(balances, root3Alpha)
    res_floatpoint = mimpl.calculateInvariantAltFloatWithInfo(balances, root3Alpha)

    invariant_floatpoint = res_floatpoint['root']
    invariant_fixedpoint_float = float(invariant_fixedpoint)

    invariant_min = min(invariant_fixedpoint_float, invariant_floatpoint)

    # Estimated relative max loss to LPs if the true invariant is somewhere between the two estimates.
    diff = abs(invariant_fixedpoint_float - invariant_floatpoint) / invariant_min

    assert diff == pytest.approx(0.0, abs=1e-13)
