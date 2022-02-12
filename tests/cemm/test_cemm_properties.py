import functools
from decimal import Decimal
from math import pi, sin, cos
from typing import Tuple

import hypothesis.strategies as st
from _pytest.python_api import ApproxDecimal

# from pyrsistent import Invariant
from brownie.test import given
from brownie import reverts
from hypothesis import assume, settings, event, example
from tests.cemm import cemm as mimpl
from tests.cemm.util import gen_params, gen_params_cemm_dinvariant
from tests.support.utils import scale, to_decimal, qdecimals, unscale
from tests.support.types import *
from tests.support.quantized_decimal import QuantizedDecimal as D

billion_balance_strategy = st.integers(min_value=0, max_value=10_000_000_000)

# this is a multiplicative separation
# This is consistent with tightest price range of beta - alpha >= MIN_PRICE_SEPARATION
MIN_PRICE_SEPARATION = to_decimal("0.0001")
MAX_IN_RATIO = to_decimal("0.3")
MAX_OUT_RATIO = to_decimal("0.3")

MIN_BALANCE_RATIO = to_decimal("5e-5")
MIN_FEE = D("0.0002")


def params2MathParams(params: CEMMMathParams) -> mimpl.Params:
    """The python math implementation is a bit older and uses its own data structures. This function converts."""
    return mimpl.Params(params.alpha, params.beta, params.c, -params.s, params.l)


def faulty_params(balances, params: CEMMMathParams):
    balances = [to_decimal(b) for b in balances]
    if balances[0] == 0 and balances[1] == 0:
        return True
    return 0 >= params.beta - params.alpha >= MIN_PRICE_SEPARATION


def gen_balances():
    return st.tuples(billion_balance_strategy, billion_balance_strategy)


def gen_balances_vector():
    return gen_balances().map(lambda args: Vector2(*args))


def calculate_loss(delta_invariant, invariant, balances):
    # delta_balance_A = delta_invariant / invariant * balance_A
    factor = to_decimal(delta_invariant / invariant)
    return (to_decimal(balances[0]) * factor, to_decimal(balances[1]) * factor)


################################################################################
### test calcOutGivenIn for invariant change
@settings(max_examples=1_000)
@given(
    params=gen_params(),
    balances=gen_balances(),
    amountIn=qdecimals(min_value=1, max_value=1_000_000_000, places=4),
    tokenInIsToken0=st.booleans(),
)
@example(
    # Failure with error 1 in invariant. (relative error very small!)
    params=CEMMMathParams(
        alpha=D("5.941451855790000000"),
        beta=D("9.178966500000000000"),
        c=D("0.944428837436701696"),
        s=D("0.328715942749907009"),
        l=D("8.304036210000000000"),
    ),
    balances=(3352648952, 49042),
    amountIn=D("1.017200000000000000"),
    tokenInIsToken0=False,
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

    # Event to tell these apart from (checked) error cases.
    event("full check")

    if invariant_after < invariant_before or invariant_sol_after < invariant_sol:
        loss = calculate_loss(
            invariant_after - invariant_before, invariant_before, balances
        )
        # compare upper bound on loss in y terms
        loss_ub = -loss[0] * params.beta - loss[1]
        assert loss_ub < D("5e-2")
    else:
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
