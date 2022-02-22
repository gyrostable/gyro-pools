from decimal import Decimal
from typing import Tuple

import hypothesis.strategies as st
from brownie import reverts
from brownie.test import given
from hypothesis import assume
from tests.cpmmv2 import math_implementation
from tests.libraries import pool_math_implementation
from tests.support.utils import scale, to_decimal

billion_balance_strategy = st.integers(min_value=0, max_value=1_000_000_000)

# this is a multiplicative separation
# This is consistent with tightest price range of 0.9999 - 1.0001
MIN_SQRTPARAM_SEPARATION = to_decimal("1.0001")


def faulty_params(balances, sqrt_alpha, sqrt_beta):
    balances = [to_decimal(b) for b in balances]
    if balances[0] == 0 and balances[1] == 0:
        return True
    return sqrt_beta <= sqrt_alpha * MIN_SQRTPARAM_SEPARATION


@given(
    balances=st.tuples(billion_balance_strategy, billion_balance_strategy),
    sqrt_alpha=st.decimals(min_value="0.02", max_value="0.99995", places=4),
    sqrt_beta=st.decimals(min_value="1.00005", max_value="1.8", places=4),
    delta_balances=st.tuples(billion_balance_strategy, billion_balance_strategy),
)
def test_liquidity_invariant_update(
    gyro_two_math_testing,
    balances: Tuple[int, int],
    sqrt_alpha,
    sqrt_beta,
    delta_balances: Tuple[int, int],
):

    if faulty_params(balances, sqrt_alpha, sqrt_beta):
        return

    last_invariant = math_implementation.calculateInvariant(
        to_decimal(balances), to_decimal(sqrt_alpha), to_decimal(sqrt_beta)
    )

    new_invariant = pool_math_implementation.liquidityInvariantUpdate(
        to_decimal(balances),
        to_decimal(last_invariant),
        to_decimal(delta_balances),
        True,
    )

    if new_invariant < 0:
        return

    new_invariant_sol = gyro_two_math_testing.liquidityInvariantUpdate(
        scale(balances),
        scale(last_invariant),
        scale(delta_balances),
        True,
    )

    assert to_decimal(new_invariant_sol) == scale(new_invariant).approxed()
