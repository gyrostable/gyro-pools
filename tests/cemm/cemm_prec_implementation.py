from operator import add, sub
from typing import Iterable

import pytest
from tests.support.quantized_decimal import QuantizedDecimal as D
from tests.libraries.signed_fixed_point import add_mag, mul_array
from tests.support.utils import scale, unscale

_MAX_IN_RATIO = D("0.3")
_MAX_OUT_RATIO = D("0.3")


class Params:
    alpha: D
    beta: D
    c: D
    s: D
    l: D


class DerivedParams:
    tauAlpha: tuple[D, D]
    tauBeta: tuple[D, D]


def virtualOffset0(p: Params, d: DerivedParams, invariant: D) -> D:
    if d.tauBeta[0] > 0:
        a = D(invariant).mul_up(p.l).mul_up(d.tauBeta[0]).mul_up(p.c)
    else:
        a = D(invariant) * p.l * d.tauBeta[0] * p.c
    if d.tauBeta[1] > 0:
        a += D(invariant).mul_up(p.s).mul_up(d.tauBeta[1])
    else:
        a += D(invariant) * p.s * d.tauBeta[1]
    return a


def virtualOffset1(p: Params, d: DerivedParams, invariant: D) -> D:
    if d.tauAlpha[0] < 0:
        b = D(invariant).mul_up(p.l).mul_up(-d.tauAlpha[0]).mul_up(p.s)
    else:
        b = -D(invariant) * p.l * d.tauAlpha[0] * p.s
    if d.tauAlpha[1] > 0:
        b += D(invariant).mul_up(p.c).mul_up(d.tauAlpha[1])
    else:
        b += D(invariant) * p.c * d.tauAlpha[1]
    return b


def calcAChi_x(p: Params, d: DerivedParams) -> D:
    return (
        p.s * p.c * (d.tauBeta[1] - d.tauAlpha[1]) / p.l
        + d.tauBeta[0] * p.c * p.c
        + d.tauAlpha[0] * p.s * p.s
    )


def calcAChiDivLambda_y(p: Params, d: DerivedParams) -> D:
    return (
        p.s * p.c * (d.tauBeta[0] - d.tauAlpha[0])
        + (p.s * p.s * d.tauBeta[1] + p.c * p.c * d.tauAlpha[1]) / p.l
    )


def calcAtAChi(x: D, y: D, p: Params, d: DerivedParams, AChi_x: D) -> D:
    val = (x * p.c / p.l - D(y).mul_up(D(p.s)).div_up(D(p.l))) * AChi_x
    val += (x * p.l * p.s + y * p.l * p.c) * p.s * p.c * (d.tauBeta[0] - d.tauAlpha[0])
    val += (x * p.s + y * p.c) * (p.s * p.s * d.tauBeta[1] + p.c * p.c * d.tauAlpha[1])
    return val


def calcAChiAChi(p: Params, AChi_x: D, AChiDivLambda_y: D) -> D:
    val = D(add_mag(AChi_x, D("7e-18")))
    val = val.mul_up(val)
    term = D(add_mag(AChiDivLambda_y, D("8e-18")))
    term = D(p.l).mul_up(D(p.l)).mul_up(term).mul_up(term)
    return val + term


def calcMinAtxAChiySqPlusAtxSq(x: D, y: D, p: Params, AChiDivLambda_y: D) -> D:
    val = D(x).mul_up(x).mul_up(p.c).mul_up(p.c) + D(y).mul_up(y).mul_up(p.s).mul_up(
        p.s
    )
    val -= x * y * (2 * p.c) * p.s

    term = add_mag(AChiDivLambda_y, D("8e-18"))
    return -val.mul_up(term).mul_up(term) + (val - D("1e-17")) / p.l / p.l


def calc2AtxAtyAChixAChiy(x: D, y: D, p: Params, AChi_x: D, AChiDivLambda_y: D) -> D:
    val = (x * x - y * y) * p.c * (2 * p.s) + y * x * ((p.c * p.c - p.s * p.s) * 2)
    return val * AChi_x * AChiDivLambda_y


def calcMinAtyAChixSqPlusAtySq(x: D, y: D, p: Params, AChi_x: D) -> D:
    val = D(x).mul_up(x).mul_up(p.s).mul_up(p.s) + D(y).mul_up(y).mul_up(p.c).mul_up(
        p.c
    )
    val += D(x).mul_up(y).mul_up(p.s * 2).mul_up(p.c)
    term = D(add_mag(AChi_x, D("7e-18")))
    return -val.mul_up(term).mul_up(term) + (val - D("1e-17"))


def calcInvariantSqrt(x: D, y: D, p: Params, AChi_x: D, AChiDivLambda_y: D) -> D:
    val = (
        calcMinAtxAChiySqPlusAtxSq(x, y, p, AChiDivLambda_y)
        + calc2AtxAtyAChixAChiy(x, y, p, AChi_x, AChiDivLambda_y)
        + calcMinAtyAChixSqPlusAtySq(x, y, p, AChi_x)
    )
    val -= D("100e-18")
    if val < 0:
        val = 0
    return D(val).sqrt()


def calculateInvariant(balances: Iterable[D], p: Params, d: DerivedParams) -> D:
    x, y = (D(balances[0]), D(balances[1]))
    AChi_x = calcAChi_x(p, d)
    AChiDivLambda_y = calcAChiDivLambda_y(p, d)
    AtAChi = calcAtAChi(x, y, p, d, AChi_x)
    sqrt = calcInvariantSqrt(x, y, p, AChi_x, AChiDivLambda_y)
    denominator = calcAChiAChi(p, AChi_x, AChiDivLambda_y) - 1
    assert denominator > 0
    return (AtAChi + sqrt) / denominator


def mul_xp_in_xylambda(x: D, y: D, lam: D, round_up: bool):
    # do these in int operations to be exact
    (xi, yi, lami) = (int(x * D("1e18")), int(y * D("1e18")), int(lam * D("1e3")))
    prod = xi * yi * lami
    if round_up:
        if prod == 0:  # a weird exception case in Python b/c // is floor integer
            result = 1
        else:
            result = int(prod - 1) // int(D("1e21")) + 1
        return unscale(D(result))
    else:
        return unscale(D(prod // int(D("1e21"))))


def mul_xp_in_xylambdalambda(x: D, y: D, lam: D, round_up: bool) -> D:
    (xi, yi, lami) = (int(x * D("1e18")), int(y * D("1e18")), int(lam * D("1e3")))
    prod = xi * yi * lami
    if round_up:
        if prod == 0:  # a weird exception case in Python b/c // is floor integer
            result = 1
        else:
            result = (prod - 1) // int(D("1e13")) + 1
        prod = result * lami
        result = (prod - 1) // int(D("1e11")) + 1
        return unscale(D(result))
    else:
        prod = prod // int(D("1e13"))
        prod = prod * lami
        result = prod // int(D("1e11"))
        return unscale(D(result))


def calcXpXp(x: D, r: D, lam: D, s: D, c: D, tauBeta: Iterable[D], roundUp: bool) -> D:
    muls = (mul_xp_in_xylambdalambda(r, r, lam, roundUp), tauBeta[0], tauBeta[0], c, c)
    xx = mul_array(muls, roundUp)

    if roundUp:
        roundUpMag = tauBeta[0] * tauBeta[1] < 0
    else:
        roundUpMag = tauBeta[0] * tauBeta[1] > 0
    muls = (
        mul_xp_in_xylambda(r, r, 2 * lam, roundUpMag),
        c,
        s,
        tauBeta[0],
        tauBeta[1],
    )
    xx += mul_array(muls, roundUp)

    if roundUp:
        roundUpMag = tauBeta[0] < 0
    else:
        roundUpMag = tauBeta[0] > 0
    muls = (-mul_xp_in_xylambda(r, x, 2 * lam, roundUpMag), c, tauBeta[0])
    xx += mul_array(muls, roundUp)

    muls = (r, r, s, s, tauBeta[1], tauBeta[1])
    xx += mul_array(muls, roundUp)

    muls = (-r, x, s * 2, tauBeta[1])
    xx += mul_array(muls, roundUp)

    if roundUp:
        xx += D(x).mul_up(x)
    else:
        xx += x * x
    return xx
