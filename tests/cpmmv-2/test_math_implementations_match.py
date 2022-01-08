from decimal import Decimal
from typing import Tuple

import hypothesis.strategies as st
from brownie.test import given

import math_implementation
from tests.support.utils import scale, to_decimal


billion_balance_strategy = st.integers(min_value=0, max_value=1_000_000_000)


@given(
    balances=st.tuples(billion_balance_strategy, billion_balance_strategy),
    sqrt_alpha=st.decimals(min_value="0.9", max_value="0.9999", places=4),
    sqrt_beta=st.decimals(min_value="0.02", max_value="1.8", places=4),
)
def test_calculate_quadratic_terms_balances(
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


# def test_calculate_quadratic_terms_balances2(gyro_two_math_testing):

#     balances = list(pairwise(random.sample(range(1, 1000000000), 100)))
#     # alphas = [random.uniform(0.5, 1) for v in range(10)]

#     for balance in balances:
#         balances = [scale(balance[0]), scale(balance[1])]
#         sqrt_alpha = scale('0.5')
#         sqrt_beta = scale('1.5')

#         (a, mb, mc) = math_implementation.calculateQuadraticTerms(
#             balances, sqrt_alpha, sqrt_beta)

#         balances_sol = [balance[0] * 10 ** 18, balance[1] * 10 ** 18]
#         sqrt_alpha_sol = 0.5e18
#         sqrt_beta_sol = 1.5e18

#         (a_sol, mb_sol, mc_sol) = gyro_two_math_testing.calculateQuadraticTerms(
#             balances_sol, sqrt_alpha_sol, sqrt_beta_sol)

#         assert scale(a) == D(a_sol)
#         # assert mb == mb_sol //WHY???
#         assert mc == scale(mc_sol)
