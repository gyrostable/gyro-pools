from decimal import Decimal
from decimal import Decimal
from math import pi, sin, cos

import hypothesis.strategies as st
import pytest

# from pyrsistent import Invariant
from brownie.test import given
from hypothesis import assume, example

from tests.support.util_common import (
    BasicPoolParameters,
    gen_balances,
    gen_balances_vector,
)
from tests.cemm import cemm as mimpl
from tests.cemm import cemm_prec_implementation as prec_impl
from tests.support.quantized_decimal import QuantizedDecimal as D
from tests.support.types import *
from tests.support.utils import scale, to_decimal, qdecimals, unscale
from tests.cemm import util

from math import pi, sin, cos, tan, acos


from tests.support.types import Vector2

billion_balance_strategy = st.integers(min_value=0, max_value=100_000_000_000)

MIN_PRICE_SEPARATION = to_decimal("0.0001")
MAX_IN_RATIO = to_decimal("0.3")
MAX_OUT_RATIO = to_decimal("0.3")

MIN_BALANCE_RATIO = to_decimal("5e-5")
MIN_FEE = D("0.0002")


bpool_params = BasicPoolParameters(
    MIN_PRICE_SEPARATION, MAX_IN_RATIO, MAX_OUT_RATIO, MIN_BALANCE_RATIO, MIN_FEE
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
def test_calcAChi(gyro_cemm_math_testing, params):
    mparams = util.params2MathParams(params)
    derived = util.mathParams2DerivedParams(mparams)
    result_py = prec_impl.calcAChi_x(params, derived)
    result_sol = gyro_cemm_math_testing.calcAChi_x(scale(params), scale(derived))
    assert result_py == unscale(result_sol)

    result2_py = prec_impl.calcAChiDivLambda_y(params, derived)
    result2_sol = gyro_cemm_math_testing.calcAChiDivLambda_y(
        scale(params), scale(derived)
    )
    assert result2_py == unscale(result2_sol)

    result3_py = prec_impl.calcAChiAChi(params, result_py, result2_py)
    result3_sol = gyro_cemm_math_testing.calcAChiAChi(
        scale(params), scale(result_py), scale(result2_py)
    )
    assert result3_py == unscale(result3_sol)

    # test against the old (imprecise) implementation
    chi = Vector2(
        mparams.Ainv_times(derived.tauBeta[0], derived.tauBeta[1])[0],
        mparams.Ainv_times(derived.tauAlpha[0], derived.tauAlpha[1])[1],
    )
    AChi = mparams.A_times(chi[0], chi[1])
    assert result_py == AChi[0].approxed()
    assert result2_py == (AChi[1] / params.l).approxed()


@given(
    params=gen_params(),
    balances=gen_balances(2, bpool_params),
)
def test_calcAtAChi(gyro_cemm_math_testing, params, balances):
    mparams = util.params2MathParams(params)
    derived = util.mathParams2DerivedParams(mparams)
    AChi_x = prec_impl.calcAChi_x(params, derived)
    AChiDivLambda_y = prec_impl.calcAChiDivLambda_y(params, derived)
    result_py = prec_impl.calcAtAChi(balances[0], balances[1], params, derived, AChi_x)
    result_sol = gyro_cemm_math_testing.calcAtAChi(
        scale(balances[0]),
        scale(balances[1]),
        scale(params),
        scale(derived),
        scale(AChi_x),
    )
    assert result_py == unscale(result_sol)


@given(
    params=gen_params_conservative(),
    balances=gen_balances(2, bpool_params),
)
def test_calcAtAChi_sense_check(params, balances):
    mparams = util.params2MathParams(params)
    derived = util.mathParams2DerivedParams(mparams)
    AChi_x = prec_impl.calcAChi_x(params, derived)
    AChiDivLambda_y = prec_impl.calcAChiDivLambda_y(params, derived)
    result_py = prec_impl.calcAtAChi(balances[0], balances[1], params, derived, AChi_x)
    # test against the old (imprecise) implementation
    At = mparams.A_times(balances[0], balances[1])
    AtAChi = At[0] * AChi_x + At[1] * AChiDivLambda_y * params.l
    assert AtAChi == result_py.approxed()


@given(
    params=gen_params(),
    balances=gen_balances(2, bpool_params),
)
def test_calcMinAtxAChiySqPlusAtxSq(gyro_cemm_math_testing, params, balances):
    mparams = util.params2MathParams(params)
    derived = util.mathParams2DerivedParams(mparams)
    AChiDivLambda_y = prec_impl.calcAChiDivLambda_y(params, derived)
    result_py = prec_impl.calcMinAtxAChiySqPlusAtxSq(
        balances[0], balances[1], params, AChiDivLambda_y
    )
    result_sol = gyro_cemm_math_testing.calcMinAtxAChiySqPlusAtxSq(
        scale(balances[0]), scale(balances[1]), scale(params), scale(AChiDivLambda_y)
    )
    assert result_py == unscale(result_sol)


@given(
    params=gen_params(),
    balances=gen_balances(2, bpool_params),
)
def test_calc2AtxAtyAChixAChiy(gyro_cemm_math_testing, params, balances):
    mparams = util.params2MathParams(params)
    derived = util.mathParams2DerivedParams(mparams)
    AChi_x = prec_impl.calcAChi_x(params, derived)
    AChiDivLambda_y = prec_impl.calcAChiDivLambda_y(params, derived)
    result_py = prec_impl.calc2AtxAtyAChixAChiy(
        balances[0], balances[1], params, AChi_x, AChiDivLambda_y
    )
    result_sol = gyro_cemm_math_testing.calc2AtxAtyAChixAChiy(
        scale(balances[0]),
        scale(balances[1]),
        scale(params),
        scale(AChi_x),
        scale(AChiDivLambda_y),
    )
    assert result_py == unscale(result_sol)


@given(
    params=gen_params(),
    balances=gen_balances(2, bpool_params),
)
def test_calcMinAtyAChixSqPlusAtySq(gyro_cemm_math_testing, params, balances):
    mparams = util.params2MathParams(params)
    derived = util.mathParams2DerivedParams(mparams)
    AChi_x = prec_impl.calcAChi_x(params, derived)
    result_py = prec_impl.calcMinAtyAChixSqPlusAtySq(
        balances[0], balances[1], params, AChi_x
    )
    result_sol = gyro_cemm_math_testing.calcMinAtyAChixSqPlusAtySq(
        scale(balances[0]), scale(balances[1]), scale(params), scale(AChi_x)
    )
    assert result_py == unscale(result_sol)


@given(
    params=gen_params(),
    balances=gen_balances(2, bpool_params),
)
def test_calcInvariantSqrt(gyro_cemm_math_testing, params, balances):
    mparams = util.params2MathParams(params)
    derived = util.mathParams2DerivedParams(mparams)
    AChi_x = prec_impl.calcAChi_x(params, derived)
    AChiDivLambda_y = prec_impl.calcAChiDivLambda_y(params, derived)
    result_py = prec_impl.calcInvariantSqrt(
        balances[0], balances[1], params, AChi_x, AChiDivLambda_y
    )
    result_sol = gyro_cemm_math_testing.calcInvariantSqrt(
        scale(balances[0]),
        scale(balances[1]),
        scale(params),
        scale(AChi_x),
        scale(AChiDivLambda_y),
    )
    assert result_py == unscale(result_sol).approxed(rel=D("1e-13"))


@given(
    params=gen_params(),
    balances=gen_balances(2, bpool_params),
)
def test_calculateInvariant(gyro_cemm_math_testing, params, balances):
    mparams = util.params2MathParams(params)
    derived = util.mathParams2DerivedParams(mparams)
    result_py = prec_impl.calculateInvariant(balances, params, derived)
    result_sol = gyro_cemm_math_testing.calculateInvariant(
        scale(balances), scale(params), scale(derived)
    )
    assert result_py == unscale(result_sol).approxed(rel=D("1e-12"))


@given(
    params=gen_params_conservative(),
    balances=gen_balances(2, bpool_params),
)
def test_calculateInvariant_sense_check(params, balances):
    mparams = util.params2MathParams(params)
    derived = util.mathParams2DerivedParams(mparams)
    result_py = prec_impl.calculateInvariant(balances, params, derived)
    # test against the old (imprecise) implementation
    cemm = mimpl.CEMM.from_x_y(balances[0], balances[1], mparams)
    assert cemm.r == result_py.approxed()


@given(
    params=gen_params(),
    invariant=st.decimals(min_value="1e-5", max_value="1e12", places=4),
)
def test_virtualOffsets(gyro_cemm_math_testing, params, invariant):
    mparams = util.params2MathParams(params)
    derived = util.mathParams2DerivedParams(mparams)
    a_py = prec_impl.virtualOffset0(params, derived, invariant)
    b_py = prec_impl.virtualOffset1(params, derived, invariant)
    a_sol = gyro_cemm_math_testing.virtualOffset0(
        scale(params), scale(derived), scale(invariant)
    )
    b_sol = gyro_cemm_math_testing.virtualOffset1(
        scale(params), scale(derived), scale(invariant)
    )
    assert a_py == unscale(a_sol)
    assert b_py == unscale(b_sol)

    # test against the old (imprecise) implementation
    midprice = (mparams.alpha + mparams.beta) / D(2)
    cemm = mimpl.CEMM.from_px_r(midprice, invariant, mparams)
    assert a_py == cemm.a.approxed()
    assert b_py == cemm.b.approxed()


@given(params=gen_params(), balances=gen_balances(2, bpool_params))
def test_calcXpXpDivLambdaLambda(gyro_cemm_math_testing, params, balances):
    mparams = util.params2MathParams(params)
    derived = util.mathParams2DerivedParams(mparams)
    invariant = prec_impl.calculateInvariant(balances, params, derived)
    a = prec_impl.virtualOffset0(params, derived, invariant * (D(1) + D("1e-12")))
    b = prec_impl.virtualOffset1(params, derived, invariant * (D(1) + D("1e-12")))

    XpXp_py = prec_impl.calcXpXpDivLambdaLambda(
        balances[0], invariant, params.l, params.s, params.c, a, derived.tauBeta
    )
    XpXp_sol = gyro_cemm_math_testing.calcXpXpDivLambdaLambda(
        scale(balances[0]),
        scale(invariant),
        scale(params.l),
        scale(params.s),
        scale(params.c),
        scale(a),
        scale(derived.tauBeta),
    )
    assert XpXp_py == unscale(XpXp_sol)

    # sense test
    a_py = prec_impl.virtualOffset0(params, derived, invariant)
    XpXp = (balances[0] - a_py) * (balances[0] - a_py) / params.l / params.l
    assert XpXp == XpXp_py.approxed()


@given(params=gen_params(), balances=gen_balances(2, bpool_params))
def test_calcYpYpDivLambdaLambda(gyro_cemm_math_testing, params, balances):
    mparams = util.params2MathParams(params)
    derived = util.mathParams2DerivedParams(mparams)
    invariant = prec_impl.calculateInvariant(balances, params, derived)
    a = prec_impl.virtualOffset0(params, derived, invariant * (D(1) + D("1e-12")))
    b = prec_impl.virtualOffset1(params, derived, invariant * (D(1) + D("1e-12")))

    tau_beta = Vector2(-derived.tauAlpha[0], derived.tauAlpha[1])
    YpYp_py = prec_impl.calcXpXpDivLambdaLambda(
        balances[1], invariant, params.l, params.c, params.s, a, tau_beta
    )
    YpYp_sol = gyro_cemm_math_testing.calcXpXpDivLambdaLambda(
        scale(balances[1]),
        scale(invariant),
        scale(params.l),
        scale(params.c),
        scale(params.s),
        scale(a),
        scale(tau_beta),
    )
    assert YpYp_py == unscale(YpYp_sol)

    # sense test
    b_py = prec_impl.virtualOffset1(params, derived, invariant)
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
    mparams = util.params2MathParams(params)
    derived = util.mathParams2DerivedParams(mparams)
    invariant = prec_impl.calculateInvariant(balances, params, derived)
    a = prec_impl.virtualOffset0(params, derived, invariant * (D(1) + D("1e-12")))
    b = prec_impl.virtualOffset1(params, derived, invariant * (D(1) + D("1e-12")))
    # the error comes from the square root and from the square root in r (in the offset)
    # these are amplified by the invariant, lambda, and/or balances
    # note that r can be orders of magnitude greater than balances
    error_tolx = max(
        invariant * params.l * params.s, invariant, balances[0] / params.l / params.l
    ) * D("5e-13")
    error_toly = max(
        invariant * params.l * params.c, invariant, balances[1] / params.l / params.l
    ) * D("5e-13")

    val_py = prec_impl.solveQuadraticSwap(
        params.l, balances[0], params.s, params.c, invariant, [a, b], derived.tauBeta
    )
    val_sol = gyro_cemm_math_testing.solveQuadraticSwap(
        scale(params.l),
        scale(balances[0]),
        scale(params.s),
        scale(params.c),
        scale(invariant),
        scale([a, b]),
        scale(derived.tauBeta),
    )
    assert val_py <= unscale(val_sol)
    assert val_py == unscale(val_sol).approxed(abs=error_tolx)

    tau_beta = Vector2(-derived.tauAlpha[0], derived.tauAlpha[1])
    val_y_py = prec_impl.solveQuadraticSwap(
        params.l, balances[1], params.c, params.s, invariant, [b, a], tau_beta
    )
    val_y_sol = gyro_cemm_math_testing.solveQuadraticSwap(
        scale(params.l),
        scale(balances[1]),
        scale(params.c),
        scale(params.s),
        scale(invariant),
        scale([b, a]),
        scale(tau_beta),
    )
    assert val_y_py <= unscale(val_y_sol)
    assert val_y_py == unscale(val_y_sol).approxed(abs=error_toly)


# note: only test this for conservative parameters b/c old implementation is so imprecise
@given(params=gen_params_conservative(), balances=gen_balances(2, bpool_params))
def test_solveQuadraticSwap_sense_check(params, balances):
    mparams = util.params2MathParams(params)
    derived = util.mathParams2DerivedParams(mparams)
    invariant = prec_impl.calculateInvariant(balances, params, derived)
    a = prec_impl.virtualOffset0(params, derived, invariant)
    b = prec_impl.virtualOffset1(params, derived, invariant)

    val_py = prec_impl.solveQuadraticSwap(
        params.l, balances[0], params.s, params.c, invariant, [a, b], derived.tauBeta
    )
    tau_beta = Vector2(-derived.tauAlpha[0], derived.tauAlpha[1])
    val_y_py = prec_impl.solveQuadraticSwap(
        params.l, balances[1], params.c, params.s, invariant, [b, a], tau_beta
    )

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
    mparams = util.params2MathParams(params)
    derived = util.mathParams2DerivedParams(mparams)
    invariant = prec_impl.calculateInvariant(balances, params, derived)

    error_tolx = max(
        invariant * params.l * params.s, invariant, balances[0] / params.l / params.l
    ) * D("5e-13")
    error_toly = max(
        invariant * params.l * params.c, invariant, balances[1] / params.l / params.l
    ) * D("5e-13")

    y_py = prec_impl.calcYGivenX(balances[0], params, derived, invariant)
    y_sol = gyro_cemm_math_testing.calcYGivenX(
        scale(balances[0]), scale(params), scale(derived), scale(invariant)
    )
    assert y_py <= unscale(y_sol)
    assert y_py == unscale(y_sol).approxed(abs=error_tolx)

    x_py = prec_impl.calcXGivenY(balances[1], params, derived, invariant)
    x_sol = gyro_cemm_math_testing.calcXGivenY(
        scale(balances[1]), scale(params), scale(derived), scale(invariant)
    )
    assert x_py <= unscale(x_sol)
    assert x_py == unscale(x_sol).approxed(abs=error_toly)


@given(params=gen_params_conservative(), balances=gen_balances(2, bpool_params))
def test_calcYGivenX_sense_check(params, balances):
    mparams = util.params2MathParams(params)
    derived = util.mathParams2DerivedParams(mparams)
    invariant = prec_impl.calculateInvariant(balances, params, derived)

    y_py = prec_impl.calcYGivenX(balances[0], params, derived, invariant)
    x_py = prec_impl.calcXGivenY(balances[1], params, derived, invariant)

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
    mparams = util.params2MathParams(params)
    derived = util.mathParams2DerivedParams(mparams)
    invariant = prec_impl.calculateInvariant(balances, params, derived)

    xp_py = prec_impl.maxBalances0(params, derived, invariant)
    yp_py = prec_impl.maxBalances1(params, derived, invariant)
    xp_sol = gyro_cemm_math_testing.maxBalances0(
        scale(params), scale(derived), scale(invariant)
    )
    yp_sol = gyro_cemm_math_testing.maxBalances1(
        scale(params), scale(derived), scale(invariant)
    )
    assert xp_py == unscale(xp_sol)
    assert yp_py == unscale(yp_sol)

    # sense test against old implementation
    midprice = (mparams.alpha + mparams.beta) / D(2)
    cemm = mimpl.CEMM.from_px_r(midprice, invariant, mparams)

    assert xp_py == D(cemm.xmax).approxed()
    assert yp_py == D(cemm.ymax).approxed()
