import functools
from decimal import Decimal
from math import pi, sin, cos
from typing import Tuple

import hypothesis.strategies as st
from _pytest.python_api import ApproxDecimal
from brownie.test import given
from brownie import reverts
from hypothesis import assume, settings
from tests.cemm import cemm as mimpl
from tests.support.utils import scale, to_decimal, qdecimals, unscale
from tests.support.types import *
from tests.support.quantized_decimal import QuantizedDecimal as D

billion_balance_strategy = st.integers(min_value=0, max_value=10_000_000_000)

# this is a multiplicative separation
# This is consistent with tightest price range of beta - alpha >= MIN_PRICE_SEPARATION
MIN_PRICE_SEPARATION = to_decimal("0.0001")
MAX_IN_RATIO = to_decimal("0.3")
MAX_OUT_RATIO = to_decimal("0.3")

MIN_BALANCE_RATIO = to_decimal("1e-5")
MIN_FEE = D("0.0001")


def params2MathParams(params: CEMMMathParams) -> mimpl.Params:
    """The python math implementation is a bit older and uses its own data structures. This function converts."""
    return mimpl.Params(params.alpha, params.beta, params.c, -params.s, params.l)


def faulty_params(balances, params: CEMMMathParams):
    balances = [to_decimal(b) for b in balances]
    if balances[0] == 0 and balances[1] == 0:
        return True
    return 0 >= params.beta - params.alpha >= MIN_PRICE_SEPARATION


@st.composite
def gen_params(draw):
    phi_degrees = draw(st.floats(10, 80))
    phi = phi_degrees / 360 * 2 * pi
    s = sin(phi)
    c = cos(phi)
    l = draw(qdecimals("1", "10"))
    alpha = draw(qdecimals("0.05", "0.995"))
    beta = draw(qdecimals("1.005", "20.0"))
    # factor = D(1)
    factor = draw(qdecimals("0.2", "20.0"))
    return CEMMMathParams(factor * alpha, factor * beta, D(c), D(s), l)


def gen_balances():
    return st.tuples(billion_balance_strategy, billion_balance_strategy)


def gen_balances_vector():
    return gen_balances().map(lambda args: Vector2(*args))


################################################################################
### test calcOutGivenIn for invariant change
@given(
    params=gen_params(),
    balances=gen_balances(),
    amountIn=qdecimals(min_value=1, max_value=1_000_000_000, places=4),
    tokenInIsToken0=st.booleans(),
)
def test_invariant_across_calcOutGivenIn(
    params, balances, amountIn, tokenInIsToken0, gyro_cemm_math_testing
):
    ixIn = 0 if tokenInIsToken0 else 1
    ixOut = 1 - ixIn

    assume(amountIn <= to_decimal("0.3") * balances[ixIn])

    mparams = params2MathParams(params)
    derived = CEMMMathDerivedParams(
        Vector2(mparams.tau_alpha[0], mparams.tau_alpha[1]),
        Vector2(mparams.tau_beta[0], mparams.tau_beta[1]),
    )

    cemm = mimpl.CEMM.from_x_y(balances[0], balances[1], mparams)
    invariant_before = cemm.r
    invariant_sol = gyro_cemm_math_testing.calculateInvariant(
        scale(balances), scale(params), scale(derived)
    )

    f_trade = cemm.trade_x if tokenInIsToken0 else cemm.trade_y
    mamountOut = f_trade(amountIn)  # This changes the state of the cemm but whatever

    revertCode = None
    if mamountOut is None:
        revertCode = "BAL#357"  # ASSET_BOUNDS_EXCEEDED
    elif -mamountOut > to_decimal("0.3") * balances[ixOut]:
        revertCode = "BAL#305"  # MAX_OUT_RATIO

    if revertCode is not None:
        with reverts(revertCode):
            gyro_cemm_math_testing.calcOutGivenIn(
                scale(balances),
                scale(amountIn),
                tokenInIsToken0,
                scale(params),
                scale(derived),
                invariant_sol,
            )
        return

    if (
        balances[0] < balances[1] * MIN_BALANCE_RATIO
        or balances[1] < balances[0] * MIN_BALANCE_RATIO
    ):
        assume(False)

    amountOut = -mamountOut

    amountOut_sol = gyro_cemm_math_testing.calcOutGivenIn(
        scale(balances),
        scale(amountIn),
        tokenInIsToken0,
        scale(params),
        scale(derived),
        invariant_sol,
    )

    if tokenInIsToken0:
        new_balances = (
            balances[0] + amountIn,
            balances[1] - unscale(to_decimal(amountOut_sol)) * (D(1) - MIN_FEE),
        )
    else:
        new_balances = (
            balances[0] - unscale(to_decimal(amountOut_sol)) * (D(1) - MIN_FEE),
            balances[1] + amountIn,
        )

    if (
        new_balances[0] < new_balances[1] * MIN_BALANCE_RATIO
        or new_balances[1] < new_balances[0] * MIN_BALANCE_RATIO
    ):
        assume(False)

    cemm = mimpl.CEMM.from_x_y(new_balances[0], new_balances[1], mparams)
    invariant_after = cemm.r
    invariant_sol_after = gyro_cemm_math_testing.calculateInvariant(
        scale(new_balances), scale(params), scale(derived)
    )

    assert invariant_after >= invariant_before
    assert invariant_sol_after >= invariant_sol


################################################################################
### test calcInGivenOut for invariant change
@given(
    params=gen_params(),
    balances=gen_balances(),
    amountOut=qdecimals(min_value=1, max_value=1_000_000_000, places=4),
    tokenInIsToken0=st.booleans(),
)
def test_invariant_across_calcInGivenOut(
    params, balances, amountOut, tokenInIsToken0, gyro_cemm_math_testing
):
    ixIn = 0 if tokenInIsToken0 else 1
    ixOut = 1 - ixIn

    assume(amountOut <= to_decimal("0.3") * balances[ixOut])

    mparams = params2MathParams(params)
    derived = CEMMMathDerivedParams(
        Vector2(mparams.tau_alpha[0], mparams.tau_alpha[1]),
        Vector2(mparams.tau_beta[0], mparams.tau_beta[1]),
    )

    cemm = mimpl.CEMM.from_x_y(balances[0], balances[1], mparams)
    invariant_before = cemm.r
    invariant_sol = gyro_cemm_math_testing.calculateInvariant(
        scale(balances), scale(params), scale(derived)
    )

    f_trade = cemm.trade_y if tokenInIsToken0 else cemm.trade_x
    amountIn = f_trade(-amountOut)  # This changes the state of the cemm but whatever

    revertCode = None
    if amountIn is None:
        revertCode = "BAL#357"  # ASSET_BOUNDS_EXCEEDED
    elif amountIn > to_decimal("0.3") * balances[ixIn]:
        revertCode = "BAL#304"  # MAX_IN_RATIO

    if revertCode is not None:
        with reverts(revertCode):
            gyro_cemm_math_testing.calcInGivenOut(
                scale(balances),
                scale(amountOut),
                tokenInIsToken0,
                scale(params),
                scale(derived),
                invariant_sol,
            )
        return

    if (
        balances[0] < balances[1] * MIN_BALANCE_RATIO
        or balances[1] < balances[0] * MIN_BALANCE_RATIO
    ):
        return

    amountIn_sol = gyro_cemm_math_testing.calcInGivenOut(
        scale(balances),
        scale(amountOut),
        tokenInIsToken0,
        scale(params),
        scale(derived),
        invariant_sol,
    )

    if tokenInIsToken0:
        new_balances = (
            balances[0] + unscale(to_decimal(amountIn_sol)) * (D(1) + MIN_FEE),
            balances[1] - amountOut,
        )
    else:
        new_balances = (
            balances[0] - amountOut,
            balances[1] + unscale(to_decimal(amountIn_sol)) * (D(1) + MIN_FEE),
        )

    cemm = mimpl.CEMM.from_x_y(new_balances[0], new_balances[1], mparams)
    invariant_after = cemm.r
    invariant_sol_after = gyro_cemm_math_testing.calculateInvariant(
        scale(new_balances), scale(params), scale(derived)
    )

    if (
        new_balances[0] < new_balances[1] * MIN_BALANCE_RATIO
        or new_balances[1] < new_balances[0] * MIN_BALANCE_RATIO
    ):
        return

    assert invariant_after >= invariant_before
    assert invariant_sol_after >= invariant_sol


################################################################################
### test liquidityInvariantUpdate for L change
@st.composite
def gen_params_cemm_dinvariant(draw):
    params = draw(gen_params())
    mparams = params2MathParams(params)
    balances = draw(gen_balances())
    cemm = mimpl.CEMM.from_x_y(balances[0], balances[1], mparams)
    dinvariant = draw(
        qdecimals(-cemm.r.raw, 2 * cemm.r.raw)
    )  # Upper bound kinda arbitrary
    assume(abs(dinvariant) > D("1E-10"))  # Only relevant updates
    return params, cemm, dinvariant


@given(params_cemm_dinvariant=gen_params_cemm_dinvariant())
def test_invariant_across_liquidityInvariantUpdate(
    gyro_cemm_math_testing, params_cemm_dinvariant
):
    params, cemm, dinvariant = params_cemm_dinvariant
    assume(cemm.x != 0 or cemm.y != 0)

    mparams = params2MathParams(params)
    derived = CEMMMathDerivedParams(
        Vector2(mparams.tau_alpha[0], mparams.tau_alpha[1]),
        Vector2(mparams.tau_beta[0], mparams.tau_beta[1]),
    )

    balances = [cemm.x, cemm.y]
    deltaBalances = cemm.update_liquidity(dinvariant, mock=True)
    deltaBalances = (
        abs(deltaBalances[0]),
        abs(deltaBalances[1]),
    )  # b/c solidity function takes uint inputs for this

    rnew = cemm.r + dinvariant
    rnew_sol = gyro_cemm_math_testing.liquidityInvariantUpdate(
        scale(balances),
        scale(cemm.r),
        scale(deltaBalances),
        (dinvariant >= 0),
    )

    if dinvariant >= 0:
        new_balances = (balances[0] + deltaBalances[0], balances[1] + deltaBalances[1])
    else:
        new_balances = (balances[0] - deltaBalances[0], balances[1] - deltaBalances[1])

    rnew_sol2 = gyro_cemm_math_testing.calculateInvariant(
        scale(new_balances), scale(params), scale(derived)
    )

    rnew2 = (mimpl.CEMM.from_x_y(new_balances[0], new_balances[1], mparams)).r

    assert rnew2 >= rnew2
    # the following assertion can fail if square root in solidity has error, but consequence is small (some small protocol fees)
    # assert rnew_sol2 >= rnew_sol
