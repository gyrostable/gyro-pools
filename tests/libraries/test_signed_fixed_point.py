from decimal import Decimal
from typing import Tuple

import hypothesis.strategies as st
from brownie import reverts
from brownie.test import given
from hypothesis import assume
from tests.libraries import signed_fixed_point
from tests.support.utils import scale, to_decimal, unscale

from tests.support.quantized_decimal import QuantizedDecimal as D

billions_strategy = st.decimals(min_value="-1e12", max_value="1e12", places=4)
tens_strategy = st.decimals(min_value="-10", max_value="10", places=4)


@given(a=billions_strategy, b=st.decimals(min_value="0", max_value="1", places=4))
def test_addMag(signed_math_testing, a, b):
    a, b = (D(a), D(b))
    c_py = signed_fixed_point.add_mag(a, b)
    c_sol = signed_math_testing.addMag(scale(a), scale(b))
    assert c_py == unscale(c_sol)
