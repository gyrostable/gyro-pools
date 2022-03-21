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
    MIN_PRICE_SEPARATION,
    MAX_IN_RATIO,
    MAX_OUT_RATIO,
    MIN_BALANCE_RATIO,
    MIN_FEE,
    int(D("1e11")),
)


@st.composite
def gen_params_swap_given_in(draw):
    params = draw(util.gen_params())
    balances = draw(gen_balances(2, bpool_params))
    tokenInIsToken0 = draw(st.booleans())
    i = 0 if tokenInIsToken0 else 1
    amountIn = draw(
        qdecimals(
            min_value=min(1, D("0.2") * balances[i]),
            max_value=D("0.3") * balances[i],
        )
    )
    return params, balances, tokenInIsToken0, amountIn


@st.composite
def gen_params_swap_given_out(draw):
    params = draw(util.gen_params())
    balances = draw(gen_balances(2, bpool_params))
    tokenInIsToken0 = draw(st.booleans())
    i = 1 if tokenInIsToken0 else 0
    amountOut = draw(
        qdecimals(
            min_value=min(1, D("0.2") * balances[i]),
            max_value=D("0.3") * balances[i],
        )
    )
    return params, balances, tokenInIsToken0, amountOut


################################################################################
### test calcOutGivenIn for invariant change
# @pytest.mark.skip(reason="Imprecision error to fix")
# @settings(max_examples=1_000)
@given(
    params_swap_given_in=gen_params_swap_given_in(),
)
def test_invariant_across_calcOutGivenIn(params_swap_given_in, gyro_cemm_math_testing):
    params, balances, tokenInIsToken0, amountIn = params_swap_given_in
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
    params_swap_given_out=gen_params_swap_given_out(),
)
def test_invariant_across_calcInGivenOut(params_swap_given_out, gyro_cemm_math_testing):
    params, balances, tokenInIsToken0, amountOut = params_swap_given_out
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


@given(params_cemm_invariantUpdate=util.gen_params_cemm_liquidityUpdate())
def test_invariant_across_liquidityInvariantUpdate(
    gyro_cemm_math_testing, params_cemm_invariantUpdate
):
    util.mtest_invariant_across_liquidityInvariantUpdate(
        params_cemm_invariantUpdate, gyro_cemm_math_testing
    )
