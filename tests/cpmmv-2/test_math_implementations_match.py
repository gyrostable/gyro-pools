from decimal import Decimal
from typing import Tuple

import hypothesis.strategies as st
import pytest
from brownie.test import given
from tests.support.utils import scale, to_decimal

import math_implementation

billion_balance_strategy = st.integers(min_value=0, max_value=1_000_000_000)


@given(
    balances=st.tuples(billion_balance_strategy, billion_balance_strategy),
    sqrt_alpha=st.decimals(min_value="0.9", max_value="0.9999", places=4),
    sqrt_beta=st.decimals(min_value="0.02", max_value="1.8", places=4),
)
def test_calculate_quadratic_terms(
    gyro_two_math_testing,
    balances: Tuple[int, int],
    sqrt_alpha: Decimal,
    sqrt_beta: Decimal,
):
    (a, mb, mc) = math_implementation.calculateQuadraticTerms(
        to_decimal(balances), to_decimal(sqrt_alpha), to_decimal(sqrt_beta)
    )

    if any(v < 0 for v in [a, mb, mc]):
        return

    (a_sol, mb_sol, mc_sol) = gyro_two_math_testing.calculateQuadraticTerms(
        scale(balances), scale(sqrt_alpha), scale(sqrt_beta)
    )

    assert a_sol == scale(a)
    assert mb_sol == scale(mb)
    assert mc_sol == scale(mc)


@given(
    balances=st.tuples(billion_balance_strategy, billion_balance_strategy),
    sqrt_alpha=st.decimals(min_value="0.9", max_value="0.9999", places=4),
    sqrt_beta=st.decimals(min_value="0.02", max_value="1.8", places=4),
)
def test_calculate_quadratic(gyro_two_math_testing, balances, sqrt_alpha, sqrt_beta):

    (a, mb, mc) = math_implementation.calculateQuadraticTerms(
        to_decimal(balances), to_decimal(sqrt_alpha), to_decimal(sqrt_beta)
    )

    if any(v > 0 for v in [-a, mb, mc]):
        return

    root = math_implementation.calculateQuadratic(a, mb, mc)

    root_sol = gyro_two_math_testing.calculateQuadratic(
        scale(a), scale(mb), scale(mc)
    )

    assert root == root_sol


@given(
    balances=st.tuples(billion_balance_strategy,
                       billion_balance_strategy),
    sqrt_alpha=st.decimals(min_value="0.9", max_value="0.9999", places=4),
    sqrt_beta=st.decimals(min_value="0.02", max_value="1.8", places=4),
)
def test_calculate_quadratic_special(gyro_two_math_testing, balances, sqrt_alpha, sqrt_beta):

    (a, mb, mc) = math_implementation.calculateQuadraticTerms(
        to_decimal(balances), to_decimal(sqrt_alpha), to_decimal(sqrt_beta)
    )

    if any(v < 0 for v in [a, mb, mc]):
        return

    print(a)

    root = math_implementation.calculateQuadraticSpecial(a, mb, mc)

    root_sol = gyro_two_math_testing.calculateQuadratic(
        scale(a), scale(mb), scale(mc)
    )

    assert int(root_sol) == scale(root).approxed()


@given(
    balances=st.tuples(billion_balance_strategy, billion_balance_strategy),
    sqrt_alpha=st.decimals(min_value="0.9", max_value="0.9999", places=4),
    sqrt_beta=st.decimals(min_value="0.02", max_value="1.8", places=4),
)
def test_calculate_invariant(gyro_two_math_testing, balances, sqrt_alpha, sqrt_beta):

    (a, mb, mc) = math_implementation.calculateQuadraticTerms(
        to_decimal(balances), to_decimal(sqrt_alpha), to_decimal(sqrt_beta)
    )

    if any(v < 0 for v in [a, mb, mc]):
        return

    invariant = math_implementation.calculateInvariant(
        to_decimal(balances), to_decimal(sqrt_alpha), to_decimal(sqrt_beta)
    )

    invariant_sol = gyro_two_math_testing.calculateInvariant(
        scale(balances), scale(sqrt_alpha), scale(sqrt_beta)
    )

    assert to_decimal(invariant_sol) == scale(invariant).approxed(abs=1e15)


@given(
    invariant=st.decimals(min_value="100", max_value="100000000", places=4),
    sqrt_beta=st.decimals(min_value="0.02", max_value="1.8", places=4),
)
def test_calculate_virtual_parameter_0(gyro_two_math_testing, sqrt_beta, invariant):

    virtual_parameter = math_implementation.calculateVirtualParameter0(
        invariant, sqrt_beta
    )

    virtual_parameter_sol = gyro_two_math_testing.calculateVirtualParameter0(
        scale(invariant), scale(sqrt_beta))

    assert to_decimal(virtual_parameter_sol) == scale(
        virtual_parameter).approxed()


@given(
    invariant=st.decimals(min_value="100", max_value="100000000", places=4),
    sqrt_alpha=st.decimals(min_value="0.9", max_value="0.9999", places=4),
)
def test_calculate_virtual_parameter_1(gyro_two_math_testing, sqrt_alpha, invariant):

    virtual_parameter = math_implementation.calculateVirtualParameter1(
        invariant, sqrt_alpha
    )

    virtual_parameter_sol = gyro_two_math_testing.calculateVirtualParameter1(
        scale(invariant), scale(sqrt_alpha))

    assert to_decimal(virtual_parameter_sol) == scale(
        virtual_parameter).approxed()


@given(
    invariant=st.decimals(min_value="100", max_value="100000000", places=4),
    virtual_x=st.decimals(min_value="100", max_value="1000000000", places=4),
)
def test_calculate_sqrt_price(gyro_two_math_testing, invariant, virtual_x):

    sqrt_price = math_implementation.calculateSqrtPrice(
        invariant, virtual_x
    )

    sqrt_price_sol = gyro_two_math_testing.calculateSqrtPrice(
        scale(invariant), scale(virtual_x))

    assert to_decimal(sqrt_price_sol) == scale(
        sqrt_price).approxed()


# @given(
#     balances=st.tuples(billion_balance_strategy, billion_balance_strategy),
#     last_invariant=st.decimals(
#         min_value="100", max_value="100000000", places=4),
#     sqrt_alpha=st.decimals(min_value="0.9", max_value="0.9999", places=4),
#     sqrt_beta=st.decimals(min_value="0.02", max_value="1.8", places=4),
#     diff_y=st.decimals(min_value="100", max_value="1000000000", places=4))
# def test_liquidity_invariant_update(gyro_two_math_testing, balances, sqrt_alpha, sqrt_beta, last_invariant, diff_y):

#     if any(b < 0 for b in [balances[0], balances[1]]):
#         return

#     new_invariant = math_implementation.liquidityInvariantUpdate(to_decimal(balances), sqrt_alpha,
#                                                                  sqrt_beta, last_invariant, diff_y, True)

#     new_invariant_sol = gyro_two_math_testing.liquidityInvariantUpdate(scale(balances), scale(
#         sqrt_alpha), scale(sqrt_beta), scale(last_invariant), scale(diff_y), True)

#     assert to_decimal(new_invariant_sol) == scale(
#         new_invariant).approxed()
