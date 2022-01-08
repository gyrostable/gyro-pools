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

    # if balances[0] < 1 or balances[1] < 1:
    #     return

    (a, mb, mc) = math_implementation.calculateQuadraticTerms(
        to_decimal(balances), to_decimal(sqrt_alpha), to_decimal(sqrt_beta)
    )

    if any(v < 0 for v in [a, mb, mc]):
        return

    root = math_implementation.calculateQuadraticSpecial(a, mb, mc)

    root_sol = gyro_two_math_testing.calculateQuadratic(
        scale(a), scale(mb), scale(mc)
    )

    assert int(root_sol) == scale(root).approxed()


# @given(
#     balances=st.tuples(billion_balance_strategy, billion_balance_strategy),
#     sqrt_alpha=st.decimals(min_value="0.9", max_value="0.9999", places=4),
#     sqrt_beta=st.decimals(min_value="0.02", max_value="1.8", places=4),
# )
# def test_calculate_invariant(gyro_two_math_testing, balances, sqrt_alpha, sqrt_beta):

#     (a, mb, mc) = math_implementation.calculateQuadraticTerms(
#         to_decimal(balances), to_decimal(sqrt_alpha), to_decimal(sqrt_beta)
#     )

#     if any(v < 0 for v in [a, mb, mc]):
#         return

#     invariant = math_implementation.calculateInvariant(
#         to_decimal(balances), to_decimal(sqrt_alpha), to_decimal(sqrt_beta)
#     )

#     invariant_sol = gyro_two_math_testing.calculateInvariant(
#         scale(balances), scale(sqrt_alpha), scale(sqrt_beta)
#     )

#     assert to_decimal(invariant_sol) == scale(invariant)


# @given(
#     invariant=st.decimals(min_value="0", max_value="1000000000", places=0),
#     sqrt_beta=st.decimals(min_value="0.02", max_value="1.8", places=4),
# )
# def test_calculate_virtual_parameter_0(gyro_two_math_testing, invariant, sqrt_beta):

#     if invariant == 0:
#         return
#     virtual_parameter = math_implementation.calculateVirtualParameter0(
#         to_decimal(invariant), to_decimal(sqrt_beta)
#     )

#     virtual_parameter_sol = gyro_two_math_testing.calculateVirtualParameter0(
#         invariant, sqrt_beta)

#     assert virtual_parameter_sol == scale(virtual_parameter)
