import math
import random
from itertools import tee
from typing import Iterable, Tuple, TypeVar

import pytest

import math_implementation
from quantized_decimal import QuantizedDecimal
from quantized_decimal import QuantizedDecimal as D

T = TypeVar("T")


def pairwise(iterable: Iterable[T]) -> Iterable[Tuple[T, T]]:
    """Returns an iterable of shifted pairs
    >>> list(pairwise(['a', 'b', 'c', 'd']))
    [('a', 'b'), ('b', 'c'), ('c', 'd')]
    """
    a, b = tee(iterable)
    next(b, None)
    return zip(a, b)


def scale(x, decimals=18):
    if not isinstance(x, QuantizedDecimal):
        x = QuantizedDecimal(x)
    return (x * 10 ** decimals).floor()


def test_calculate_quadratic_terms_balances(gyro_two_math_testing):

    balances = list(pairwise(random.sample(range(1, 1000000000), 100)))
    # alphas = [random.uniform(0.5, 1) for v in range(10)]

    for balance in balances:
        balances = [scale(balance[0]), scale(balance[1])]
        sqrt_alpha = scale('0.97')
        sqrt_beta = scale('1.02')

        (a, mb, mc) = math_implementation.calculateQuadraticTerms(
            balances, sqrt_alpha, sqrt_beta)

        balances_sol = [balance[0] * 10 ** 18, balance[1] * 10 ** 18]

        (a_sol, mb_sol, mc_sol) = gyro_two_math_testing.calculateQuadraticTerms(
            balances_sol, sqrt_alpha, sqrt_beta)

        assert scale(a) == D(a_sol)
        assert mb == mb_sol
        assert mc == scale(mc_sol)


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
