from logging import warning
from math import sqrt
from typing import Iterable, List, Tuple, Callable

import numpy as np
from tests.support.quantized_decimal import QuantizedDecimal as D

_MAX_IN_RATIO = D("0.3")
_MAX_OUT_RATIO = D("0.3")

prec_convergence = D("1E-18")


def calculateInvariant(balances: Iterable[D], root3Alpha: D) -> D:
    (a, mb, mc, md) = calculateCubicTerms(balances, root3Alpha)
    return calculateCubic(a, mb, mc, md, root3Alpha, balances)

def calculateCubicTerms(balances: Iterable[D], root3Alpha: D) -> tuple[D, D, D, D]:
    x, y, z = balances
    a = D(1) - root3Alpha * root3Alpha * root3Alpha
    b = -(x + y + z) * root3Alpha * root3Alpha
    c = -(x * y + y * z + z * x) * root3Alpha
    d = -x * y * z
    assert a > 0 and b < 0 and c <= 0 and d <= 0
    return a, -b, -c, -d


# Doesn't completely mirror _calculateCubic in GyroThreeMath.sol
def calculateCubic(
    a: D, mb: D, mc: D, md: D, root3Alpha: D, balances: Iterable[D]
) -> D:
    invariant, log_steps = calculateInvariantNewton(
        a, -mb, -mc, -md, root3Alpha, balances
    )
    return invariant


def calculateInvariantNewton(
    a: D, b: D, c: D, d: D, alpha1: D, balances: Iterable[D]
) -> tuple[D, list]:
    log = []
    # def test_calc_out_given_in(gyro_three_math_testing, amount_in, balances, root_three_alpha):

    #     if amount_in > to_decimal('0.3') * (balances[0]):
    #         return

    #     if faulty_params(balances, root_three_alpha):
    #         return

    #     invariant = math_implementation.calculateInvariant(
    #         to_decimal(balances), to_decimal(root_three_alpha))

    #     virtual_param_in = math_implementation.calculateVirtualParameter0(
    #         to_decimal(invariant))
    x, y, z = balances

    lmin = -b / (a * 3) + (b ** 2 - a * c * 3).sqrt() / (
        a * 3
    )  # Sqrt is not gonna make a problem b/c all summands are positive.
    # ^ Local minimum, and also the global minimum of f among l > 0; towards a starting point
    l0 = lmin * D(
        "1.5"
    )  # 1.5 is a magic number, experimentally found; it seems this becomes exact for alpha -> 1.

    l = l0
    delta = D(1)
    delta_pre = None  # Not really used, only to flag the first iteration.

    while True:
        # delta = f(l)/f'(l)
        f_l = a * l ** 3 + b * l ** 2 + c * l + d

        # Compute derived values for comparison:
        # TESTING only; could base the exit condition on this if I really wanted
        gamma = l ** 2 / ((x + l * alpha1) * (y + l * alpha1))  # 3√(px py)
        px = (z + l * alpha1) / (x + l * alpha1)
        py = (z + l * alpha1) / (y + l * alpha1)
        x1 = l * (gamma / px - alpha1)
        y1 = l * (gamma / py - alpha1)
        z1 = l * (gamma - alpha1)

        log.append(dict(l=l, delta=delta, f_l=f_l, dx=x1 - x, dy=y1 - y, dz=z1 - z))

        # if abs(f_l) < prec_convergence:
        if (
            abs(x - x1) < prec_convergence
            and abs(y - y1) < prec_convergence
            and abs(z - z1) < prec_convergence
        ):
            return l, log
        df_l = a * 3 * l ** 2 + b * 2 * l + c
        delta = f_l / df_l

        # delta==0 can happen with poor numerical precision! In this case, this is all we can get.
        if delta_pre is not None and (delta == 0 or f_l < 0):
            # warning("Early exit due to numerical instability")
            return l, log

        l -= delta
        delta_pre = delta

def invariantFunctionsFloat(balances: Iterable[D], root3Alpha: D) -> tuple[Callable, Callable]:
    a, mb, mc, md = calculateCubicTermsFloat(map(float, balances), float(root3Alpha))
    def f(l):
        # res = a * l**3 - mb * l**2 - mc * l - md
        # To prevent catastrophic elimination. Note this makes a BIG difference ito f values, but not ito computed l
        # values.
        res = ((a * l - mb) * l - mc) * l - md
        print(f" f({l})".ljust(22) + f"= {res}")
        return res
    def df(l):
        # res = 3 * a * l**2 - 2 * mb * l - mc
        res = (3 * a * l - 2 * mb) * l - mc
        print(f"df({l})".ljust(22) + f"= {res}")
        return res
    return f, df


def calculateInvariantAltFloatWithInfo(balances: Iterable[D], root3Alpha: D):
    """Alternative implementation of the invariant calculation that can't be done in Solidity. Should match
    calculateInvariant() to a high degree of accuracy.

    Version that also returns debug info.

    Don't rely on anything but the 'root' component!"""
    from scipy.optimize import root_scalar

    f, df = invariantFunctionsFloat(balances, root3Alpha)
    a, mb, mc, md = calculateCubicTermsFloat(map(float, balances), float(root3Alpha))

    # See CPMMV writeup, appendix A.1
    l_m = mb / (3*a)
    l_plus = l_m + sqrt(l_m**2 + mc)
    l_0 = 1.5 * l_plus

    res = root_scalar(f, fprime=df, x0=l_0, rtol=1e-18, xtol=1e-18)

    return dict(
        root=res.root,
        f=f,
        root_results=res,
        l_0=l_0
    )


def calculateInvariantAltFloat(balances: Iterable[D], root3Alpha: D) -> float:
    return calculateInvariantAltFloatWithInfo(balances, root3Alpha)['root']


def calculateCubicTermsFloat(balances: Iterable[float], root3Alpha: float) -> tuple[float, float, float, float]:
    x, y, z = balances
    a = 1 - root3Alpha * root3Alpha * root3Alpha
    b = -(x + y + z) * root3Alpha * root3Alpha
    c = -(x * y + y * z + z * x) * root3Alpha
    d = -x * y * z
    assert a > 0 and b < 0 and c <= 0 and d <= 0
    return a, -b, -c, -d


def maxOtherBalances(balances: List[D]) -> List[int]:
    indices = [0, 0, 0]
    if balances[0] >= balances[1]:
        if balances[0] >= balances[2]:
            indices[0] = 0
            indices[1] = 1
            indices[2] = 2
        else:
            indices[0] = 2
            indices[1] = 0
            indices[2] = 1
    else:
        if balances[1] >= balances[2]:
            indices[0] = 1
            indices[1] = 0
            indices[2] = 2
        else:
            indices[0] = 2
            indices[1] = 1
            indices[2] = 0

    return indices


def calcOutGivenIn(balanceIn: D, balanceOut: D, amountIn: D, virtualOffset: D) -> D:
    assert amountIn <= balanceIn * _MAX_IN_RATIO
    virtIn = balanceIn + virtualOffset
    virtOut = balanceOut + virtualOffset
    # minus b/c amountOut is negative
    amountOut = -(virtIn.mul_up(virtOut).div_up(virtIn + amountIn) - virtOut)
    # assert amountOut <= balanceOut * _MAX_OUT_RATIO
    return amountOut


def calcInGivenOut(balanceIn: D, balanceOut: D, amountOut: D, virtualOffset: D) -> D:
    assert amountOut <= balanceOut * _MAX_OUT_RATIO
    virtIn = balanceIn + virtualOffset
    virtOut = balanceOut + virtualOffset
    amountIn = virtIn.mul_up(virtOut).div_up(virtOut - amountOut) - virtIn
    # assert amountIn <= balanceIn * _MAX_IN_RATIO
    return amountIn
