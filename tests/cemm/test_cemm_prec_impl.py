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


from tests.support.types import Vector2

billion_balance_strategy = st.integers(min_value=0, max_value=10_000_000_000)

MIN_PRICE_SEPARATION = to_decimal("0.0001")
MAX_IN_RATIO = to_decimal("0.3")
MAX_OUT_RATIO = to_decimal("0.3")

MIN_BALANCE_RATIO = to_decimal("5e-5")
MIN_FEE = D("0.0002")


bpool_params = BasicPoolParameters(
    MIN_PRICE_SEPARATION, MAX_IN_RATIO, MAX_OUT_RATIO, MIN_BALANCE_RATIO, MIN_FEE
)

billions_strategy = st.decimals(min_value="0", max_value="1e12", places=4)
# assume lambda only has three non-zero decimals
lambda_strategy = st.decimals(min_value="1", max_value="1e8", places=3)


@given(
    x=billions_strategy,
    y=billions_strategy,
    lam=lambda_strategy,
)
def test_mulXpInXYLambda(gyro_cemm_math_testing, x, y, lam):
    (x, y, lam) = (D(x), D(y), D(lam))
    prod = x * y * lam
    prod_up_py = prec_impl.mul_xp_in_xylambda(x, y, lam, True)
    prod_up_sol = gyro_cemm_math_testing.mulXpInXYLambda(
        scale(x), scale(y), scale(lam), True
    )
    assert prod_up_py == unscale(prod_up_sol)
    assert prod_up_py == prod.approxed()

    prod_down_py = prec_impl.mul_xp_in_xylambda(x, y, lam, False)
    prod_down_sol = gyro_cemm_math_testing.mulXpInXYLambda(
        scale(x), scale(y), scale(lam), False
    )
    assert prod_down_py == unscale(prod_down_sol)
    assert prod_down_py == prod.approxed()


@given(
    x=billions_strategy,
    y=billions_strategy,
    lam=lambda_strategy,
)
def test_mulXpInXYLambdaLambda(gyro_cemm_math_testing, x, y, lam):
    (x, y, lam) = (D(x), D(y), D(lam))
    prod = x * y * lam * lam
    prod_up_py = prec_impl.mul_xp_in_xylambdalambda(x, y, lam, True)
    prod_up_sol = gyro_cemm_math_testing.mulXpInXYLambdaLambda(
        scale(x), scale(y), scale(lam), True
    )
    assert prod_up_py == unscale(prod_up_sol)
    assert prod_up_py == prod.approxed()

    prod_down_py = prec_impl.mul_xp_in_xylambdalambda(x, y, lam, False)
    prod_down_sol = gyro_cemm_math_testing.mulXpInXYLambdaLambda(
        scale(x), scale(y), scale(lam), False
    )
    assert prod_down_py == unscale(prod_down_sol)
    assert prod_down_py == prod.approxed()


@given(params=util.gen_params())
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
    params=util.gen_params(),
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

    # test against the old (imprecise) implementation
    At = mparams.A_times(balances[0], balances[1])
    AtAChi = At[0] * AChi_x + At[1] * AChiDivLambda_y * params.l
    assert AtAChi == result_py.approxed()


@given(
    params=util.gen_params(),
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
    params=util.gen_params(),
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
    params=util.gen_params(),
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
    params=util.gen_params(),
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
    params=util.gen_params(),
    balances=gen_balances(2, bpool_params),
)
def test_calculateInvariant(gyro_cemm_math_testing, params, balances):
    mparams = util.params2MathParams(params)
    derived = util.mathParams2DerivedParams(mparams)
    result_py = prec_impl.calculateInvariant(balances, params, derived)
    result_sol = gyro_cemm_math_testing.calculateInvariant(
        scale(balances), scale(params), scale(derived)
    )
    assert result_py == unscale(result_sol).approxed(rel=D("1e-13"))

    # test against the old (imprecise) implementation
    cemm = mimpl.CEMM.from_x_y(balances[0], balances[1], mparams)
    assert cemm.r == result_py.approxed()
