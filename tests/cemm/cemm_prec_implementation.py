from operator import add, sub
from typing import Iterable, NamedTuple, Tuple

import pytest
from tests.support.quantized_decimal import QuantizedDecimal as D
from tests.support.quantized_decimal_38 import QuantizedDecimal as D2
from tests.support.quantized_decimal_100 import QuantizedDecimal as D3
from tests.libraries.signed_fixed_point import add_mag, mul_array
from tests.support.utils import scale, unscale

_MAX_IN_RATIO = D("0.3")
_MAX_OUT_RATIO = D("0.3")


class Params(NamedTuple):
    alpha: D
    beta: D
    c: D
    s: D
    l: D


class DerivedParams(NamedTuple):
    tauAlpha: Tuple[D2, D2]
    tauBeta: Tuple[D2, D2]
    u: D2
    v: D2
    w: D2
    z: D2
    dSq: D2
    dAlpha: D2
    dBeta: D2


class Vector2(NamedTuple):
    x: D2
    y: D2


def virtualOffset0(p: Params, d: DerivedParams, r: Iterable[D]) -> D:
    if d.tauBeta[0] > 0:
        a = D(r[0]).mul_up(p.l).mul_up(d.tauBeta[0]).mul_up(p.c)
    else:
        a = D(r[1]) * p.l * d.tauBeta[0] * p.c
    if d.tauBeta[1] > 0:
        a += D(r[0]).mul_up(p.s).mul_up(d.tauBeta[1])
    else:
        a += D(r[1]) * p.s * d.tauBeta[1]
    return a


def virtualOffset1(p: Params, d: DerivedParams, r: Iterable[D]) -> D:
    if d.tauAlpha[0] < 0:
        b = D(r[0]).mul_up(p.l).mul_up(-d.tauAlpha[0]).mul_up(p.s)
    else:
        b = -D(r[1]) * p.l * d.tauAlpha[0] * p.s
    if d.tauAlpha[1] > 0:
        b += D(r[0]).mul_up(p.c).mul_up(d.tauAlpha[1])
    else:
        b += D(r[1]) * p.c * d.tauAlpha[1]
    return b


def calcAChi_x(p: Params, d: DerivedParams) -> D:
    return (
        p.s * p.c * (d.tauBeta[1] - d.tauAlpha[1]) / p.l
        + d.tauBeta[0] * p.c * p.c
        + d.tauAlpha[0] * p.s * p.s
    )


def maxBalances0(p: Params, d: DerivedParams, invariant: D) -> D:
    return D(invariant) * p.l * p.c * (d.tauBeta[0] - d.tauAlpha[0]) + D(
        invariant
    ) * p.s * (d.tauBeta[1] - d.tauAlpha[1])


def maxBalances1(p: Params, d: DerivedParams, invariant: D) -> D:
    return D(invariant) * p.l * p.s * (d.tauBeta[0] - d.tauAlpha[0]) + D(
        invariant
    ) * p.c * (d.tauAlpha[1] - d.tauBeta[1])


def calcAChiDivLambda_y(p: Params, d: DerivedParams) -> D:
    return (
        p.s * p.c * (d.tauBeta[0] - d.tauAlpha[0])
        + (p.s * p.s * d.tauBeta[1] + p.c * p.c * d.tauAlpha[1]) / p.l
    )


def calcAtAChi(x: D, y: D, p: Params, d: DerivedParams) -> D:
    w, z, u, v, lam, dSq = (
        D2(d.w),
        D2(d.z),
        D2(d.u),
        D2(d.v),
        D2(D(p.l).raw),
        D2(d.dSq),
    )
    termXp = (w / lam + z) / lam / dSq / dSq
    termNp = D(x) * p.c - D(y) * p.s
    val = mulDownXpToNp(termNp, termXp)

    termNp = D(x) * p.l * p.s + D(y) * p.l * p.c
    termXp = u / dSq / dSq
    val += mulDownXpToNp(termNp, termXp)

    termNp = D(x) * p.s + D(y) * p.c
    termXp = v / dSq / dSq
    val += mulDownXpToNp(termNp, termXp)
    return val


def calcAChiAChi(p: Params, d: DerivedParams, AChi_x: D, AChiDivLambda_y: D) -> D:
    w, z, u, v, lam, dSq = (
        D2(d.w),
        D2(d.z),
        D2(d.u),
        D2(d.v),
        D2(D(p.l).raw),
        D2(d.dSq),
    )

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
    denominator = calcAChiAChi(p, AChi_x, AChiDivLambda_y) - D(1)
    assert denominator > 0
    return (AtAChi + sqrt) / denominator


def calcXpXpDivLambdaLambda(
    x: D, r: Iterable[D], lam: D, s: D, c: D, tauBeta: Iterable[D]
) -> D:
    val = D(r[0]).mul_up(r[0]).mul_up(tauBeta[0]).mul_up(tauBeta[0]).mul_up(c).mul_up(c)

    if tauBeta[0] * tauBeta[1] > 0:
        q_a = (
            D(r[0])
            .mul_up(r[0])
            .mul_up(2 * s)
            .mul_up(tauBeta[1])
            .mul_up(c)
            .mul_up(tauBeta[0])
        )
    else:
        q_a = D(r[1]) * r[1] * (2 * s) * tauBeta[1] * c * tauBeta[0]

    if tauBeta[0] < 0:
        q_b = D(r[0]).mul_up(x).mul_up(2 * c).mul_up(-tauBeta[0])
    else:
        q_b = -D(r[1]) * x * (2 * c) * tauBeta[0]
    q_a = q_a + q_b

    q_b = D(r[0]).mul_up(r[0]).mul_up(s).mul_up(s).mul_up(tauBeta[1]).mul_up(tauBeta[1])
    if tauBeta[1] < 0:
        q_c = D(r[0]).mul_up(x).mul_up(2 * s).mul_up(-tauBeta[1])
    else:
        q_c = -D(r[1]) * x * (2 * s) * tauBeta[1]
    q_b = q_b + q_c + D(x).mul_up(x)

    q_b = D(q_b).div_up(lam) if q_b > 0 else q_b / lam

    q_a = q_a + q_b
    q_a = D(q_a).div_up(lam) if q_a > 0 else q_a / lam
    return val + q_a


def solveQuadraticSwap(
    lam: D, x: D, s: D, c: D, r: Iterable[D], ab: Iterable[D], tauBeta: Iterable[D]
) -> D:
    lamBar = (D(1) - (D(1) / lam / lam), D(1) - D(1).div_up(lam).div_up(lam))
    xp = x - ab[0]
    if xp > 0:
        qb = -xp * lamBar[1] * s * c
    else:
        qb = -D(xp).mul_up(lamBar[0]).mul_up(s).mul_up(c)

    sTerm = (D(1) - lamBar[1] * s * s, D(1) - lamBar[0].mul_up(s).mul_up(s))

    qc = (
        -calcXpXpDivLambdaLambda(x, r, lam, s, c, tauBeta)
        + r[1] * r[1] * sTerm[0]
        - D("100e-18")
    )
    if qc < 0:
        qc = 0
    qc = D(qc).sqrt()

    if qb - qc > 0:
        return D(qb - qc).div_up(sTerm[1]) + ab[1]
    else:
        return (qb - qc) / (sTerm[0]) + ab[1]


def calcYGivenX(x: D, p: Params, d: DerivedParams, invariant: D) -> D:
    r = (invariantOverestimate(invariant), invariant)
    a = virtualOffset0(p, d, r)
    b = virtualOffset1(p, d, r)
    y = solveQuadraticSwap(p.l, x, p.s, p.c, invariant, (a, b), d.tauBeta)
    return y


def calcXGivenY(y: D, p: Params, d: DerivedParams, invariant: D) -> D:
    r = (invariantOverestimate(invariant), invariant)
    a = virtualOffset0(p, d, r)
    b = virtualOffset1(p, d, r)
    tau_beta = (-d.tauAlpha[0], d.tauAlpha[1])
    x = solveQuadraticSwap(p.l, y, p.c, p.s, invariant, (b, a), tau_beta)
    return x


# for true value of invariant r
def calcYGivenX_true(x: D, p: Params, d: DerivedParams, invariant: D) -> D:
    r = (invariant + D("1e-18"), invariant)
    a = virtualOffset0(p, d, r)
    b = virtualOffset1(p, d, r)
    y = solveQuadraticSwap_true(p.l, x, p.s, p.c, invariant, (a, b), d.tauBeta)
    return y


def calcXGivenY_true(y: D, p: Params, d: DerivedParams, invariant: D) -> D:
    r = (invariant + D("1e-18"), invariant)
    a = virtualOffset0(p, d, r)
    b = virtualOffset1(p, d, r)
    tau_beta = (-d.tauAlpha[0], d.tauAlpha[1])
    x = solveQuadraticSwap_true(p.l, y, p.c, p.s, r, (b, a), tau_beta)
    return x


def solveQuadraticSwap_true(
    lam: D, x: D, s: D, c: D, r: Iterable[D], ab: Iterable[D], tauBeta: Iterable[D]
) -> D:
    lamBar = (D(1) - (D(1) / lam / lam), D(1) - D(1).div_up(lam).div_up(lam))
    xp = x - ab[0]
    if xp > 0:
        qb = -xp * lamBar[1] * s * c
    else:
        qb = -D(xp).mul_up(lamBar[0]).mul_up(s).mul_up(c)

    sTerm = (D(1) - lamBar[1] * s * s, D(1) - lamBar[0].mul_up(s).mul_up(s))

    qc = -calcXpXpDivLambdaLambda(x, r, lam, s, c, tauBeta) + r[1] * r[1] * sTerm[0]
    if qc < 0:
        qc = 0
    qc = D(qc).sqrt()

    if qb - qc > 0:
        return D(qb - qc).div_up(sTerm[1]) + ab[1]
    else:
        return (qb - qc) / (sTerm[0]) + ab[1]


def invariantOverestimate(rDown: D) -> D:
    return D(rDown) + D(rDown).mul_up(D("1e-12"))


def mulXp(a: int, b: int) -> int:
    product = int(a) * int(b) // int(D("1e38"))
    return product


def divXp(a: int, b: int) -> int:
    if a == 0:
        return 0
    a_inflated = int(a) * int(D("1e38"))
    return a_inflated // int(b)


def mulDownXpToNp(a: D, b: D2) -> D:
    a = int(D(a) * D("1e18"))
    b = int(b * D2("1e38"))
    b1 = b // int(D("1e19"))
    b2 = b - b1 * int(D("1e19")) if b1 != 0 else b
    prod1 = a * b1
    prod2 = a * b2
    if prod1 >= 0 and prod2 >= 0:
        prod = (prod1 + prod2 // int(D("1e19"))) // int(D("1e19"))
    else:
        # have to use double minus signs b/c of how // operator works
        prod = -((-prod1 - prod2 // int(D("1e19")) - 1) // int(D("1e19"))) - 1
    return D(prod) / D("1e18")


def mulUpXpToNp(a: D, b: D2) -> D:
    a = int(D(a) * D("1e18"))
    b = int(b * D2("1e38"))
    b1 = b // int(D("1e19"))
    b2 = b - b1 * int(D("1e19")) if b1 != 0 else b
    prod1 = a * b1
    prod2 = a * b2
    if prod1 <= 0 and prod2 <= 0:
        # have to use double minus signs b/c of how // operator works
        prod = -((-prod1 + -prod2 // int(D("1e19"))) // int(D("1e19")))
    else:
        prod = (prod1 + prod2 // int(D("1e19")) - 1) // int(D("1e19")) + 1
    return D(prod) / D("1e18")


def tauXp(p: Params, px: D, dPx: D2) -> tuple[D2, D2]:
    tauPx = [0, 0]
    tauPx[0] = (D2(px) * D2(p.c) - D2(p.s)) * dPx
    tauPx[1] = ((D2(p.s) * D2(px) + D2(p.c)) / D2(p.l)) * dPx
    return tuple(tauPx)


def calc_derived_values(p: Params) -> DerivedParams:
    s, c, lam, alpha, beta = (
        D(p.s).raw,
        D(p.c).raw,
        D(p.l).raw,
        D(p.alpha).raw,
        D(p.beta).raw,
    )
    s, c, lam, alpha, beta = (
        D3(s),
        D3(c),
        D3(lam),
        D3(alpha),
        D3(beta),
    )
    dSq = c * c + s * s
    d = dSq.sqrt()
    dAlpha = D3(1) / (
        ((c / d + alpha * s / d) ** 2 / lam ** 2 + (alpha * c / d - s / d) ** 2).sqrt()
    )
    dBeta = D3(1) / (
        ((c / d + beta * s / d) ** 2 / lam ** 2 + (beta * c / d - s / d) ** 2).sqrt()
    )
    tauAlpha = [0, 0]
    tauAlpha[0] = (alpha * c - s) * dAlpha
    tauAlpha[1] = (c + s * alpha) * dAlpha / lam

    tauBeta = [0, 0]
    tauBeta[0] = (beta * c - s) * dBeta
    tauBeta[1] = (c + s * beta) * dBeta / lam

    w = s * c * (tauBeta[1] - tauAlpha[1])
    z = c * c * tauBeta[0] + s * s * tauAlpha[0]
    u = s * c * (tauBeta[0] - tauAlpha[0])
    v = s * s * tauBeta[1] + c * c * tauAlpha[1]

    tauAlpha38 = (D2(tauAlpha[0].raw), D2(tauAlpha[1].raw))
    tauBeta38 = (D2(tauBeta[0].raw), D2(tauBeta[1].raw))
    derived = DerivedParams(
        tauAlpha=(tauAlpha38[0], tauAlpha38[1]),
        tauBeta=(tauBeta38[0], tauBeta38[1]),
        u=D2(u.raw),
        v=D2(v.raw),
        w=D2(w.raw),
        z=D2(z.raw),
        dSq=D2(dSq.raw),
        dAlpha=D2(dAlpha.raw),
        dBeta=D2(dBeta.raw),
    )
    return derived


def scale_derived_values(d: DerivedParams) -> DerivedParams:
    derived = DerivedParams(
        tauAlpha=Vector2(d.tauAlpha[0] * D2("1e38"), d.tauAlpha[1] * D2("1e38")),
        tauBeta=Vector2(d.tauBeta[0] * D2("1e38"), d.tauBeta[1] * D2("1e38")),
        u=d.u * D2("1e38"),
        v=d.v * D2("1e38"),
        w=d.w * D2("1e38"),
        z=d.z * D2("1e38"),
        dSq=d.dSq * D2("1e38"),
        dAlpha=d.dAlpha * D2("1e38"),
        dBeta=d.dBeta * D2("1e38"),
    )
    return derived


# def mkDerivedParmasXp(p: Params) -> DerivedParams:
#     tauAlpha = tauXp(p, p.alpha, p.dAlpha)
#     tauBeta = tauXp(p, p.beta, p.dBeta)
