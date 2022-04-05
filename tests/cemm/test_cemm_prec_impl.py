from decimal import Decimal
from decimal import Decimal
from math import pi, sin, cos

import hypothesis.strategies as st
import pytest

# from pyrsistent import Invariant
from brownie.test import given
from hypothesis import assume, example, settings

from tests.support.util_common import (
    BasicPoolParameters,
    gen_balances,
    gen_balances_vector,
)
from tests.cemm import cemm as mimpl
from tests.cemm import cemm_prec_implementation as prec_impl
from tests.support.quantized_decimal import QuantizedDecimal as D
from tests.support.quantized_decimal_38 import QuantizedDecimal as D2
from tests.support.quantized_decimal_100 import QuantizedDecimal as D3
from tests.support.types import *
from tests.support.utils import scale, to_decimal, qdecimals, unscale, apply_deep
from tests.cemm import util

from math import pi, sin, cos, tan, acos

from tests.support.types import Vector2

MIN_PRICE_SEPARATION = to_decimal("0.0001")
MAX_IN_RATIO = to_decimal("0.3")
MAX_OUT_RATIO = to_decimal("0.3")

MIN_BALANCE_RATIO = to_decimal("0")  # to_decimal("5e-5")
MIN_FEE = D(0) # D("0.0002")


def convert_deep_decimals(x, totype):
    """totype: one of D, D2, D3, i.e., some QuantizedDecimal implementation.

    Example: convert_deep_decimals(x, D3)"""
    def go(y):
        if isinstance(y, (D, D2, D3)):
            return totype(y.raw)
        else:
            return y
    return apply_deep(x, go)


bpool_params = BasicPoolParameters(
    MIN_PRICE_SEPARATION,
    MAX_IN_RATIO,
    MAX_OUT_RATIO,
    MIN_BALANCE_RATIO,
    MIN_FEE,
    int(D("1e11")),
)

bpool_params_conservative = BasicPoolParameters(
    MIN_PRICE_SEPARATION,
    MAX_IN_RATIO,
    MAX_OUT_RATIO,
    to_decimal("1e-5"),
    MIN_FEE,
    int(D("1e8")),
)


@st.composite
def gen_params(draw):
    phi_degrees = draw(st.floats(10, 80))
    phi = phi_degrees / 360 * 2 * pi

    # Price bounds. Choose s.t. the 'peg' lies approximately within the bounds (within 30%).
    # It'd be nonsensical if this was not the case: Why are we using an ellipse then?!
    peg = tan(phi)  # = price where the flattest point of the ellipse lies.
    peg = D(peg)
    alpha_high = peg * D("1.3")
    beta_low = peg * D("0.7")
    alpha = draw(qdecimals("0.05", alpha_high.raw))
    beta = draw(
        qdecimals(max(beta_low.raw, (alpha + MIN_PRICE_SEPARATION).raw), "20.0")
    )

    s = sin(phi)
    c = cos(phi)
    l = draw(qdecimals(min_value="1", max_value="1e8", places=3))
    return CEMMMathParams(alpha, beta, D(c), D(s), l)


@st.composite
def gen_params_conservative(draw):
    phi_degrees = draw(st.floats(10, 80))
    phi = phi_degrees / 360 * 2 * pi

    # Price bounds. Choose s.t. the 'peg' lies approximately within the bounds (within 30%).
    # It'd be nonsensical if this was not the case: Why are we using an ellipse then?!
    peg = tan(phi)  # = price where the flattest point of the ellipse lies.
    peg = D(peg)
    alpha_high = peg * D("1.3")
    beta_low = peg * D("0.7")
    alpha = draw(qdecimals("0.05", alpha_high.raw))
    beta = draw(
        qdecimals(max(beta_low.raw, (alpha + MIN_PRICE_SEPARATION).raw), "20.0")
    )

    s = sin(phi)
    c = cos(phi)
    l = draw(qdecimals("1", "10"))
    return CEMMMathParams(alpha, beta, D(c), D(s), l)


@given(params=gen_params())
def test_calcAChiAChi(gyro_cemm_math_testing, params):
    mparams = util.params2MathParams(params)
    derived_m = util.mathParams2DerivedParams(mparams)

    derived = prec_impl.calc_derived_values(params)
    derived_scaled = prec_impl.scale_derived_values(derived)

    result_py = prec_impl.calcAChiAChi(params, derived)
    result_sol = gyro_cemm_math_testing.calcAChiAChi(scale(params), derived_scaled)
    assert result_py == unscale(result_sol)
    assert result_py > 1

    # test against the old (imprecise) implementation
    chi = (
        mparams.Ainv_times(derived_m.tauBeta.x, derived_m.tauBeta.y)[0],
        mparams.Ainv_times(derived_m.tauAlpha.x, derived_m.tauAlpha.y)[1],
    )
    AChi = mparams.A_times(chi[0], chi[1])
    AChiAChi = AChi[0] ** 2 + AChi[1] ** 2
    assert result_py == AChiAChi.approxed()


@given(
    params=gen_params(),
    balances=gen_balances(2, bpool_params),
)
def test_calcAtAChi(gyro_cemm_math_testing, params, balances):
    derived = prec_impl.calc_derived_values(params)
    derived_scaled = prec_impl.scale_derived_values(derived)
    result_py = prec_impl.calcAtAChi(balances[0], balances[1], params, derived)
    result_sol = gyro_cemm_math_testing.calcAtAChi(
        scale(balances[0]),
        scale(balances[1]),
        scale(params),
        derived_scaled,
    )
    assert result_py == unscale(result_sol)


@given(
    params=gen_params_conservative(),
    balances=gen_balances(2, bpool_params_conservative),
)
def test_calcAtAChi_sense_check(params, balances):
    mparams = util.params2MathParams(params)
    derived_m = util.mathParams2DerivedParams(mparams)

    derived = prec_impl.calc_derived_values(params)
    result_py = prec_impl.calcAtAChi(balances[0], balances[1], params, derived)

    # test against the old (imprecise) implementation
    At = mparams.A_times(balances[0], balances[1])
    chi = (
        mparams.Ainv_times(derived_m.tauBeta.x, derived_m.tauBeta.y)[0],
        mparams.Ainv_times(derived_m.tauAlpha.x, derived_m.tauAlpha.y)[1],
    )
    AChi = mparams.A_times(chi[0], chi[1])
    AtAChi = At[0] * AChi[0] + At[1] * AChi[1]
    assert AtAChi == result_py.approxed()


@given(
    params=gen_params(),
    balances=gen_balances(2, bpool_params),
)
def test_calcMinAtxAChiySqPlusAtxSq(gyro_cemm_math_testing, params, balances):
    derived = prec_impl.calc_derived_values(params)
    derived_scaled = prec_impl.scale_derived_values(derived)
    result_py = prec_impl.calcMinAtxAChiySqPlusAtxSq(
        balances[0], balances[1], params, derived
    )
    result_sol = gyro_cemm_math_testing.calcMinAtxAChiySqPlusAtxSq(
        scale(balances[0]), scale(balances[1]), scale(params), derived_scaled
    )
    assert result_py == unscale(result_sol)


@given(
    params=gen_params_conservative(),
    balances=gen_balances(2, bpool_params_conservative),
)
def test_calcMinAtxAChiySqPlusAtxSq_sense_check(params, balances):
    mparams = util.params2MathParams(params)
    derived_m = util.mathParams2DerivedParams(mparams)

    derived = prec_impl.calc_derived_values(params)
    result_py = prec_impl.calcMinAtxAChiySqPlusAtxSq(
        balances[0], balances[1], params, derived
    )
    # test against the old (imprecise) implementation
    At = mparams.A_times(balances[0], balances[1])
    chi = (
        mparams.Ainv_times(derived_m.tauBeta.x, derived_m.tauBeta.y)[0],
        mparams.Ainv_times(derived_m.tauAlpha.x, derived_m.tauAlpha.y)[1],
    )
    AChi = mparams.A_times(chi[0], chi[1])
    val_sense = At[0] * At[0] * (1 - AChi[1] * AChi[1])
    assert result_py == val_sense.approxed()


@given(
    params=gen_params(),
    balances=gen_balances(2, bpool_params),
)
def test_calc2AtxAtyAChixAChiy(gyro_cemm_math_testing, params, balances):
    derived = prec_impl.calc_derived_values(params)
    derived_scaled = prec_impl.scale_derived_values(derived)

    result_py = prec_impl.calc2AtxAtyAChixAChiy(
        balances[0], balances[1], params, derived
    )
    result_sol = gyro_cemm_math_testing.calc2AtxAtyAChixAChiy(
        scale(balances[0]), scale(balances[1]), scale(params), derived_scaled
    )
    assert result_py == unscale(result_sol)


@given(
    params=gen_params_conservative(),
    balances=gen_balances(2, bpool_params_conservative),
)
def test_calc2AtxAtyAChixAChiy_sense_check(params, balances):
    mparams = util.params2MathParams(params)
    derived_m = util.mathParams2DerivedParams(mparams)

    derived = prec_impl.calc_derived_values(params)
    result_py = prec_impl.calc2AtxAtyAChixAChiy(
        balances[0], balances[1], params, derived
    )
    # test against the old (imprecise) implementation
    At = mparams.A_times(balances[0], balances[1])
    chi = (
        mparams.Ainv_times(derived_m.tauBeta.x, derived_m.tauBeta.y)[0],
        mparams.Ainv_times(derived_m.tauAlpha.x, derived_m.tauAlpha.y)[1],
    )
    AChi = mparams.A_times(chi[0], chi[1])
    val_sense = D(2) * At[0] * At[1] * AChi[0] * AChi[1]
    assert result_py == val_sense.approxed()


@given(
    params=gen_params(),
    balances=gen_balances(2, bpool_params),
)
def test_calcMinAtyAChixSqPlusAtySq(gyro_cemm_math_testing, params, balances):
    derived = prec_impl.calc_derived_values(params)
    derived_scaled = prec_impl.scale_derived_values(derived)
    result_py = prec_impl.calcMinAtyAChixSqPlusAtySq(
        balances[0], balances[1], params, derived
    )
    result_sol = gyro_cemm_math_testing.calcMinAtyAChixSqPlusAtySq(
        scale(balances[0]), scale(balances[1]), scale(params), derived_scaled
    )
    assert result_py == unscale(result_sol)


@given(
    params=gen_params_conservative(),
    balances=gen_balances(2, bpool_params_conservative),
)
def test_calcMinAtyAChixSqPlusAtySq_sense_check(params, balances):
    mparams = util.params2MathParams(params)
    derived_m = util.mathParams2DerivedParams(mparams)

    derived = prec_impl.calc_derived_values(params)
    result_py = prec_impl.calcMinAtyAChixSqPlusAtySq(
        balances[0], balances[1], params, derived
    )
    # test against the old (imprecise) implementation
    At = mparams.A_times(balances[0], balances[1])
    chi = (
        mparams.Ainv_times(derived_m.tauBeta.x, derived_m.tauBeta.y)[0],
        mparams.Ainv_times(derived_m.tauAlpha.x, derived_m.tauAlpha.y)[1],
    )
    AChi = mparams.A_times(chi[0], chi[1])
    val_sense = At[1] * At[1] * (D(1) - AChi[0] * AChi[0])
    assert result_py == val_sense.approxed()


@given(
    params=gen_params(),
    balances=gen_balances(2, bpool_params),
)
def test_calcInvariantSqrt(gyro_cemm_math_testing, params, balances):
    derived = prec_impl.calc_derived_values(params)
    derived_scaled = prec_impl.scale_derived_values(derived)
    result_py, err_py = prec_impl.calcInvariantSqrt(
        balances[0], balances[1], params, derived
    )
    result_sol, err_sol = gyro_cemm_math_testing.calcInvariantSqrt(
        scale(balances[0]), scale(balances[1]), scale(params), derived_scaled
    )
    assert result_py == unscale(result_sol).approxed(abs=D("5e-18"))  # (rel=D("1e-13"))
    assert err_py == unscale(err_sol)


@given(
    params=gen_params(),
    balances=gen_balances(2, bpool_params),
)
def test_calculateInvariant(gyro_cemm_math_testing, params, balances):
    derived = prec_impl.calc_derived_values(params)
    derived_scaled = prec_impl.scale_derived_values(derived)
    result_py, err_py = prec_impl.calculateInvariantWithError(balances, params, derived)
    result_sol, err_sol = gyro_cemm_math_testing.calculateInvariantWithError(
        scale(balances), scale(params), derived_scaled
    )
    denominator = prec_impl.calcAChiAChi(params, derived) - D(1)
    err = D("5e-18") if denominator > 1 else D("5e-18") / D(denominator)
    assert result_py == unscale(result_sol).approxed(abs=(err + D("500e-18")))
    assert err_py == unscale(err_sol).approxed(abs=D("500e-18"))
    # assert result_py == (result_py + err_py).approxed(rel=D("1e-12"), abs=D("1e-12"))


@given(
    params=gen_params_conservative(),
    balances=gen_balances(2, bpool_params_conservative),
)
def test_calculateInvariant_sense_check(params, balances):
    mparams = util.params2MathParams(params)

    derived = prec_impl.calc_derived_values(params)
    result_py, err_py = prec_impl.calculateInvariantWithError(balances, params, derived)
    # test against the old (imprecise) implementation
    cemm = mimpl.CEMM.from_x_y(balances[0], balances[1], mparams)
    assert cemm.r == result_py.approxed()
    assert cemm.r == D(result_py + err_py).approxed()


@given(
    params=gen_params(),
    invariant=st.decimals(min_value="1e-5", max_value="1e12", places=4),
)
def test_virtualOffsets(gyro_cemm_math_testing, params, invariant):
    derived = prec_impl.calc_derived_values(params)
    derived_scaled = prec_impl.scale_derived_values(derived)

    r = (prec_impl.invariantOverestimate(invariant), invariant)
    a_py = prec_impl.virtualOffset0(params, derived, r)
    b_py = prec_impl.virtualOffset1(params, derived, r)
    a_sol = gyro_cemm_math_testing.virtualOffset0(
        scale(params), derived_scaled, scale(r)
    )
    b_sol = gyro_cemm_math_testing.virtualOffset1(
        scale(params), derived_scaled, scale(r)
    )
    assert a_py == unscale(a_sol)
    assert b_py == unscale(b_sol)

    # test against the old (imprecise) implementation
    mparams = util.params2MathParams(params)
    midprice = (mparams.alpha + mparams.beta) / D(2)
    cemm = mimpl.CEMM.from_px_r(midprice, invariant, mparams)
    assert a_py == cemm.a.approxed()
    assert b_py == cemm.b.approxed()


@given(params=gen_params(), balances=gen_balances(2, bpool_params))
def test_calcXpXpDivLambdaLambda(gyro_cemm_math_testing, params, balances):
    derived = prec_impl.calc_derived_values(params)
    derived_scaled = prec_impl.scale_derived_values(derived)

    invariant, err = prec_impl.calculateInvariantWithError(balances, params, derived)
    r = (invariant + 2 * D(err), invariant)

    XpXp_py = prec_impl.calcXpXpDivLambdaLambda(
        balances[0], r, params.l, params.s, params.c, derived.tauBeta, derived.dSq
    )
    XpXp_sol = gyro_cemm_math_testing.calcXpXpDivLambdaLambda(
        scale(balances[0]),
        scale(r),
        scale(params.l),
        scale(params.s),
        scale(params.c),
        derived_scaled.tauBeta,
        derived_scaled.dSq,
    )
    assert XpXp_py == unscale(XpXp_sol)


@given(
    params=gen_params_conservative(),
    balances=gen_balances(2, bpool_params_conservative),
)
def test_calcXpXpDivLambdaLambda_sense_check(params, balances):
    derived = prec_impl.calc_derived_values(params)

    invariant, err = prec_impl.calculateInvariantWithError(balances, params, derived)
    r = (invariant + 2 * D(err), invariant)

    XpXp_py = prec_impl.calcXpXpDivLambdaLambda(
        balances[0], r, params.l, params.s, params.c, derived.tauBeta, derived.dSq
    )

    # sense test
    a_py = prec_impl.virtualOffset0(params, derived, r)
    XpXp = (balances[0] - a_py) * (balances[0] - a_py) / params.l / params.l
    assert XpXp == XpXp_py.approxed()


@given(params=gen_params(), balances=gen_balances(2, bpool_params))
def test_calcYpYpDivLambdaLambda(gyro_cemm_math_testing, params, balances):
    derived = prec_impl.calc_derived_values(params)
    derived_scaled = prec_impl.scale_derived_values(derived)

    invariant, err = prec_impl.calculateInvariantWithError(balances, params, derived)
    r = (invariant + 2 * D(err), invariant)

    tau_beta = Vector2(-derived.tauAlpha[0], derived.tauAlpha[1])
    tau_beta_scaled = Vector2(-derived_scaled.tauAlpha[0], derived_scaled.tauAlpha[1])
    YpYp_py = prec_impl.calcXpXpDivLambdaLambda(
        balances[1], r, params.l, params.c, params.s, tau_beta, derived.dSq
    )
    YpYp_sol = gyro_cemm_math_testing.calcXpXpDivLambdaLambda(
        scale(balances[1]),
        scale(r),
        scale(params.l),
        scale(params.c),
        scale(params.s),
        tau_beta_scaled,
        derived_scaled.dSq,
    )
    assert YpYp_py == unscale(YpYp_sol)


@given(
    params=gen_params_conservative(),
    balances=gen_balances(2, bpool_params_conservative),
)
def test_calcYpYpDivLambdaLambda_sense_check(params, balances):
    derived = prec_impl.calc_derived_values(params)

    invariant, err = prec_impl.calculateInvariantWithError(balances, params, derived)
    r = (invariant + 2 * D(err), invariant)

    tau_beta = Vector2(-derived.tauAlpha[0], derived.tauAlpha[1])
    YpYp_py = prec_impl.calcXpXpDivLambdaLambda(
        balances[1], r, params.l, params.c, params.s, tau_beta, derived.dSq
    )

    # sense test
    b_py = prec_impl.virtualOffset1(params, derived, r)
    YpYp = (balances[1] - b_py) * (balances[1] - b_py) / params.l / params.l
    assert YpYp == YpYp_py.approxed()


@given(params=gen_params(), balances=gen_balances(2, bpool_params))
@example(
    params=CEMMMathParams(
        alpha=Decimal("0.050000000000000000"),
        beta=Decimal("0.123428886495925482"),
        c=Decimal("0.984807753012208020"),
        s=Decimal("0.173648177666930331"),
        l=Decimal("17746.178000000000000000"),
    ),
    balances=[1, 1],
)
def test_solveQuadraticSwap(gyro_cemm_math_testing, params, balances):
    derived = prec_impl.calc_derived_values(params)
    derived_scaled = prec_impl.scale_derived_values(derived)

    invariant, err = prec_impl.calculateInvariantWithError(balances, params, derived)
    r = (invariant + 2 * D(err), invariant)
    a = prec_impl.virtualOffset0(params, derived, r)
    b = prec_impl.virtualOffset1(params, derived, r)
    # the error comes from the square root and from the square root in r (in the offset)
    # these are amplified by the invariant, lambda, and/or balances
    # note that r can be orders of magnitude greater than balances
    # error_tolx = max(
    #     invariant * params.l * params.s, invariant, balances[0] / params.l / params.l
    # ) * D("5e-13")
    # error_toly = max(
    #     invariant * params.l * params.c, invariant, balances[1] / params.l / params.l
    # ) * D("5e-13")

    val_py = prec_impl.solveQuadraticSwap(
        params.l,
        balances[0],
        params.s,
        params.c,
        r,
        [a, b],
        derived.tauBeta,
        derived.dSq,
    )
    val_sol = gyro_cemm_math_testing.solveQuadraticSwap(
        scale(params.l),
        scale(balances[0]),
        scale(params.s),
        scale(params.c),
        scale(r),
        scale([a, b]),
        derived_scaled.tauBeta,
        derived_scaled.dSq,
    )
    assert val_py <= unscale(val_sol)
    assert val_py == unscale(val_sol).approxed(
        abs=D("5e-18")
    )  # .approxed(abs=error_tolx)

    tau_beta = Vector2(-derived.tauAlpha[0], derived.tauAlpha[1])
    tau_beta_scaled = Vector2(-derived_scaled.tauAlpha[0], derived_scaled.tauAlpha[1])
    val_y_py = prec_impl.solveQuadraticSwap(
        params.l, balances[1], params.c, params.s, r, [b, a], tau_beta, derived.dSq
    )
    val_y_sol = gyro_cemm_math_testing.solveQuadraticSwap(
        scale(params.l),
        scale(balances[1]),
        scale(params.c),
        scale(params.s),
        scale(r),
        scale([b, a]),
        tau_beta_scaled,
        derived_scaled.dSq,
    )
    assert val_y_py <= unscale(val_y_sol)
    assert val_y_py == unscale(val_y_sol).approxed(
        abs=D("5e-18")
    )  # .approxed(abs=error_toly)


# note: only test this for conservative parameters b/c old implementation is so imprecise
@given(
    params=gen_params_conservative(),
    balances=gen_balances(2, bpool_params_conservative),
)
def test_solveQuadraticSwap_sense_check(params, balances):
    derived = prec_impl.calc_derived_values(params)

    invariant, err = prec_impl.calculateInvariantWithError(balances, params, derived)
    r = (invariant + 2 * D(err), invariant)
    a = prec_impl.virtualOffset0(params, derived, r)
    b = prec_impl.virtualOffset1(params, derived, r)

    val_py = prec_impl.solveQuadraticSwap(
        params.l,
        balances[0],
        params.s,
        params.c,
        r,
        [a, b],
        derived.tauBeta,
        derived.dSq,
    )
    tau_beta = Vector2(-derived.tauAlpha[0], derived.tauAlpha[1])
    val_y_py = prec_impl.solveQuadraticSwap(
        params.l, balances[1], params.c, params.s, r, [b, a], tau_beta, derived.dSq
    )

    mparams = util.params2MathParams(params)
    # sense test against old implementation
    midprice = (params.alpha + params.beta) / 2
    cemm = mimpl.CEMM.from_px_r(midprice, invariant, mparams)  # Price doesn't matter.
    y = cemm._compute_y_for_x(balances[0])
    assume(y is not None)  # O/w out of bounds for this invariant
    assume(balances[0] > 0 and y > 0)
    assert y == val_py.approxed(rel=D("1e-5"))

    # sense test against old implementation
    midprice = (params.alpha + params.beta) / 2
    cemm = mimpl.CEMM.from_px_r(midprice, invariant, mparams)  # Price doesn't matter.
    x = cemm._compute_x_for_y(balances[1])
    assume(x is not None)  # O/w out of bounds for this invariant
    assume(balances[1] > 0 and x > 0)
    assert x == val_y_py.approxed(rel=D("1e-5"))


# also tests calcXGivenY
@given(params=gen_params(), balances=gen_balances(2, bpool_params))
def test_calcYGivenX(gyro_cemm_math_testing, params, balances):
    derived = prec_impl.calc_derived_values(params)
    derived_scaled = prec_impl.scale_derived_values(derived)
    invariant, err = prec_impl.calculateInvariantWithError(balances, params, derived)
    r = (invariant + 2 * D(err), invariant)

    # error_tolx = max(
    #     invariant * params.l * params.s, invariant, balances[0] / params.l / params.l
    # ) * D("5e-13")
    # error_toly = max(
    #     invariant * params.l * params.c, invariant, balances[1] / params.l / params.l
    # ) * D("5e-13")

    y_py = prec_impl.calcYGivenX(balances[0], params, derived, r)
    y_sol = gyro_cemm_math_testing.calcYGivenX(
        scale(balances[0]), scale(params), derived_scaled, scale(r)
    )
    assert y_py <= unscale(y_sol)
    assert y_py == unscale(y_sol).approxed(abs=D("5e-18"))  # .approxed(abs=error_tolx)

    x_py = prec_impl.calcXGivenY(balances[1], params, derived, r)
    x_sol = gyro_cemm_math_testing.calcXGivenY(
        scale(balances[1]), scale(params), derived_scaled, scale(r)
    )
    assert x_py <= unscale(x_sol)
    assert x_py == unscale(x_sol).approxed(abs=D("5e-18"))  # .approxed(abs=error_toly)


# @settings(max_examples=1000)
@given(params=gen_params(), balances=gen_balances(2, bpool_params))
def test_calcYGivenX_property(params, balances):
    derived = prec_impl.calc_derived_values(params)
    invariant, err = prec_impl.calculateInvariantWithError(balances, params, derived)
    r = (invariant + 2 * D(err), invariant)

    y_py = prec_impl.calcYGivenX(balances[0], params, derived, r)
    assert y_py >= balances[1]

    x_py = prec_impl.calcXGivenY(balances[1], params, derived, r)
    assert x_py >= balances[0]


@given(
    params=gen_params_conservative(),
    balances=gen_balances(2, bpool_params_conservative),
)
def test_calcYGivenX_sense_check(params, balances):
    derived = prec_impl.calc_derived_values(params)
    invariant, err = prec_impl.calculateInvariantWithError(balances, params, derived)
    r = (invariant + 2 * D(err), invariant)

    y_py = prec_impl.calcYGivenX(balances[0], params, derived, r)
    x_py = prec_impl.calcXGivenY(balances[1], params, derived, r)

    mparams = util.params2MathParams(params)
    # sense test against old implementation
    midprice = (params.alpha + params.beta) / 2
    cemm = mimpl.CEMM.from_px_r(midprice, invariant, mparams)  # Price doesn't matter.
    y = cemm._compute_y_for_x(balances[0])
    assume(y is not None)  # O/w out of bounds for this invariant
    assume(balances[0] > 0 and y > 0)
    assert y == y_py.approxed(rel=D("1e-4"))

    # sense test against old implementation
    midprice = (params.alpha + params.beta) / 2
    cemm = mimpl.CEMM.from_px_r(midprice, invariant, mparams)  # Price doesn't matter.
    x = cemm._compute_x_for_y(balances[1])
    assume(x is not None)  # O/w out of bounds for this invariant
    assume(balances[1] > 0 and x > 0)
    assert x == x_py.approxed(rel=D("1e-4"))


@given(params=gen_params(), balances=gen_balances(2, bpool_params))
def test_maxBalances(gyro_cemm_math_testing, params, balances):
    derived = prec_impl.calc_derived_values(params)
    derived_scaled = prec_impl.scale_derived_values(derived)
    invariant, err = prec_impl.calculateInvariantWithError(balances, params, derived)
    r = (invariant + 2 * D(err), invariant)

    xp_py = prec_impl.maxBalances0(params, derived, r)
    yp_py = prec_impl.maxBalances1(params, derived, r)
    xp_sol = gyro_cemm_math_testing.maxBalances0(
        scale(params), derived_scaled, scale(r)
    )
    yp_sol = gyro_cemm_math_testing.maxBalances1(
        scale(params), derived_scaled, scale(r)
    )
    assert xp_py == unscale(xp_sol)
    assert yp_py == unscale(yp_sol)


@given(
    params=gen_params_conservative(),
    balances=gen_balances(2, bpool_params_conservative),
)
def test_maxBalances_sense_check(params, balances):
    derived = prec_impl.calc_derived_values(params)
    invariant, err = prec_impl.calculateInvariantWithError(balances, params, derived)
    r = (invariant + 2 * D(err), invariant)
    xp_py = prec_impl.maxBalances0(params, derived, r)
    yp_py = prec_impl.maxBalances1(params, derived, r)
    # sense test against old implementation
    mparams = util.params2MathParams(params)
    midprice = (mparams.alpha + mparams.beta) / D(2)
    cemm = mimpl.CEMM.from_px_r(midprice, invariant, mparams)

    assert xp_py == D(cemm.xmax).approxed()
    assert yp_py == D(cemm.ymax).approxed()

