import functools
from decimal import Decimal
from math import pi, sin, cos
from typing import Tuple
from unicodedata import decimal

import hypothesis.strategies as st
from _pytest.python_api import ApproxDecimal

# from pyrsistent import Invariant
from brownie.test import given
from brownie import reverts
from hypothesis import assume, settings, event, example
import pytest

from tests.support.util_common import BasicPoolParameters, gen_balances
from tests.cemm import cemm as mimpl
from tests.cemm import cemm_prec_implementation as prec_impl
from tests.cemm import util
from tests.support.utils import scale, to_decimal, qdecimals, unscale
from tests.support.types import *
from tests.support.quantized_decimal import QuantizedDecimal as D

# this is a multiplicative separation
# This is consistent with tightest price range of beta - alpha >= MIN_PRICE_SEPARATION
MIN_PRICE_SEPARATION = to_decimal("0.0001")
MAX_IN_RATIO = to_decimal("0.3")
MAX_OUT_RATIO = to_decimal("0.3")

MIN_BALANCE_RATIO = to_decimal("5e-5")
MIN_FEE = D("0.0002")

# this determines whether derivedParameters are calculated in solidity or not
DP_IN_SOL = False


bpool_params = BasicPoolParameters(
    MIN_PRICE_SEPARATION, MAX_IN_RATIO, MAX_OUT_RATIO, MIN_BALANCE_RATIO, MIN_FEE
)


################################################################################
### test calcOutGivenIn for invariant change
# @pytest.mark.skip(reason="Imprecision error to fix")
# @settings(max_examples=1_000)
@given(
    params=util.gen_params(),
    balances=gen_balances(2, bpool_params),
    amountIn=qdecimals(min_value=1, max_value=1_000_000_000, places=4),
    tokenInIsToken0=st.booleans(),
)
def test_invariant_across_calcOutGivenIn(
    params, balances, amountIn, tokenInIsToken0, gyro_cemm_math_testing
):
    # the difference is whether invariant is calculated in python or solidity, but swap calculation still in solidity
    loss_py, loss_sol = util.mtest_invariant_across_calcOutGivenIn(
        params,
        balances,
        amountIn,
        tokenInIsToken0,
        DP_IN_SOL,
        bpool_params,
        gyro_cemm_math_testing,
    )

    # compare upper bound on loss in y terms
    loss_py_ub = -loss_py[0] * params.beta - loss_py[1]
    loss_sol_ub = -loss_sol[0] * params.beta - loss_sol[1]
    assert loss_py_ub == 0  # D("5e-2")
    assert loss_sol_ub == 0  # D("5e-2")


################################################################################
### test calcInGivenOut for invariant change
# @pytest.mark.skip(reason="Imprecision error to fix")
@given(
    params=util.gen_params(),
    balances=gen_balances(2, bpool_params),
    amountOut=qdecimals(min_value=1, max_value=1_000_000_000, places=4),
    tokenInIsToken0=st.booleans(),
)
def test_invariant_across_calcInGivenOut(
    params, balances, amountOut, tokenInIsToken0, gyro_cemm_math_testing
):
    # the difference is whether invariant is calculated in python or solidity, but swap calculation still in solidity
    loss_py, loss_sol = util.mtest_invariant_across_calcInGivenOut(
        params,
        balances,
        amountOut,
        tokenInIsToken0,
        DP_IN_SOL,
        bpool_params,
        gyro_cemm_math_testing,
    )

    # compare upper bound on loss in y terms
    loss_py_ub = -loss_py[0] * params.beta - loss_py[1]
    loss_sol_ub = -loss_sol[0] * params.beta - loss_sol[1]
    assert loss_py_ub == 0  # D("5e-2")
    assert loss_sol_ub == 0  # D("5e-2")


################################################################################
### test for zero tokens in
@given(params=util.gen_params(), balances=gen_balances(2, bpool_params))
def test_zero_tokens_in(gyro_cemm_math_testing, params, balances):
    util.mtest_zero_tokens_in(gyro_cemm_math_testing, params, balances)


################################################################################
### test liquidityInvariantUpdate for L change


@pytest.mark.skip(reason="Data generation slow")
@given(params_cemm_dinvariant=util.gen_params_cemm_dinvariant())
def test_invariant_across_liquidityInvariantUpdate(
    gyro_cemm_math_testing, params_cemm_dinvariant
):
    util.mtest_invariant_across_liquidityInvariantUpdate(
        gyro_cemm_math_testing, params_cemm_dinvariant, DP_IN_SOL
    )
