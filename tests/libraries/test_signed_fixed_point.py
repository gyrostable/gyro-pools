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


@given(arr=st.tuples(billions_strategy, billions_strategy, billions_strategy))
def test_mul_array3(signed_math_testing, arr):
    mtest_mul_array(signed_math_testing, arr)


@given(
    arr=st.tuples(
        billions_strategy, billions_strategy, billions_strategy, tens_strategy
    )
)
def test_mul_array4(signed_math_testing, arr):
    mtest_mul_array(signed_math_testing, arr)


@given(
    arr=st.tuples(
        billions_strategy,
        billions_strategy,
        billions_strategy,
        tens_strategy,
        tens_strategy,
    )
)
def test_mul_array5(signed_math_testing, arr):
    mtest_mul_array(signed_math_testing, arr)


@given(
    arr=st.tuples(
        billions_strategy,
        billions_strategy,
        billions_strategy,
        tens_strategy,
        tens_strategy,
        tens_strategy,
    )
)
def test_mul_array6(signed_math_testing, arr):
    mtest_mul_array(signed_math_testing, arr)


def mtest_mul_array(signed_math_testing, arr):
    arr = list(arr)
    for i in range(len(arr)):
        arr[i] = D(arr[i])
    arr = tuple(arr)
    c = D(1)
    for i in arr:
        c = c * i

    c_mdown_py = signed_fixed_point.mul_array_down(arr)
    c_mdown_sol = signed_math_testing.mulArrayDown(scale(arr))
    assert c_mdown_py == unscale(c_mdown_sol)
    assert c_mdown_py == c.approxed()

    c_mup_py = signed_fixed_point.mul_array_up(arr)
    c_mup_sol = signed_math_testing.mulArrayUp(scale(arr))
    assert c_mup_py == unscale(c_mup_sol)
    assert c_mup_py == c.approxed()

    c_sdown_py = signed_fixed_point.mul_array(arr, False)
    c_sdown_sol = signed_math_testing.mulArray(scale(arr), False)
    assert c_sdown_py == unscale(c_sdown_sol)
    assert c_sdown_py == c.approxed()

    c_sup_py = signed_fixed_point.mul_array(arr, True)
    c_sup_sol = signed_math_testing.mulArray(scale(arr), True)
    assert c_sup_py == unscale(c_sup_sol)
    assert c_sup_py == c.approxed()
