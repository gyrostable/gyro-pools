
# We test how the python implementation reacts to an increase in precision.
# Can be run without brownie.
# NOTE: Because of brownie insanity, we can't run just this file with pytest and without loading ganache. But you can
# run it with python and then
# It will collect some diagnostics data (this is a hack).

import pandas as pd
from hypothesis import given, settings, assume, example
from hypothesis import strategies as st

from tests.cemm.util import params2MathParams, mathParams2DerivedParams, gen_params, gen_balances
from tests.support import quantized_decimal
from tests.support.quantized_decimal import QuantizedDecimal as D
from tests.support.types import CEMMMathParams
from tests.support.utils import qdecimals

import cemm as mimpl
import cemm_float as mimpl_float

MIN_BALANCE_RATIO = D("1E-5")
MIN_FEE = D("0.0000")

# Ad-hoc hack to collect error values while running tests. Should be refactored somehow at some point.
error_values = None

# MIN_BALANCE_RATIO = D(0)
# MIN_FEE = D(0)

def calculate_loss(delta_invariant, invariant, balances):
    """Loss ito. lost balances for LPs when invariant decreases by delta_invariant because of a calculation error.

    Loss = negative; gain = positive"""
    # delta_balance_A = delta_invariant / invariant * balance_A
    factor = delta_invariant / invariant
    return balances[0] * factor, balances[1] * factor

@settings(max_examples=10_000)
@given(params=gen_params())
def test_derivedParams(params):
    quantized_decimal.set_decimals(18)
    derived_single = mathParams2DerivedParams(params2MathParams(params))
    quantized_decimal.set_decimals(2*18)
    derived_double = mathParams2DerivedParams(params2MathParams(params))
    quantized_decimal.set_decimals(18)  # Compare at the lower precision (does this do anything??)
    # This passes, but with 1E-17 it doesn't pass anymore.
    assert derived_single.tauAlpha[0] == D(derived_double.tauAlpha[0].raw).approxed(abs=D('1E-16'))
    assert derived_single.tauAlpha[1] == D(derived_double.tauAlpha[1].raw).approxed(abs=D('1E-16'))
    assert derived_single.tauBeta[0] == D(derived_double.tauBeta[0].raw).approxed(abs=D('1E-16'))
    assert derived_single.tauBeta[1] == D(derived_double.tauBeta[1].raw).approxed(abs=D('1E-16'))

@settings(max_examples=20_000)
@given(
    params=gen_params(),
    balances=gen_balances(),
    amountIn=qdecimals(min_value=1, max_value=1_000_000_000, places=4),
    tokenInIsToken0=st.booleans(),
)
# The following example yields error ≥ 1E-4.
@example(
    params=CEMMMathParams(alpha=D('0.978987854300000000'), beta=D('1.005000000000000000'), c=D('0.984807753012208020'), s=D('0.173648177666930331'), l=D('9.165121265207703869')),
    balances=(402159729,
              579734344),
    amountIn=D('1.000000000000000000'),
    tokenInIsToken0=True)
def test_calcOutGivenIn(
    params, balances, amountIn, tokenInIsToken0
):
    ixIn = 0 if tokenInIsToken0 else 1
    ixOut = 1 - ixIn

    quantized_decimal.set_decimals(18)
    mparams = params2MathParams(params)
    derived = mathParams2DerivedParams(params2MathParams(params))
    cemm = mimpl.CEMM.from_x_y(balances[0], balances[1], mparams)
    r_single = cemm.r
    f_trade = cemm.trade_x if tokenInIsToken0 else cemm.trade_y
    mamountOut_single = f_trade(amountIn)
    assume(mamountOut_single is not None)

    quantized_decimal.set_decimals(2 * 18)
    mparams = params2MathParams(params)
    derived = mathParams2DerivedParams(params2MathParams(params))
    cemm = mimpl.CEMM.from_x_y(balances[0], balances[1], mparams)
    r_double = cemm.r
    f_trade = cemm.trade_x if tokenInIsToken0 else cemm.trade_y
    mamountOut_double = f_trade(amountIn)
    assert mamountOut_double is not None

    quantized_decimal.set_decimals(18)

    # assert r_single == D(r_double).approxed(abs=D('1E-14'))

    # NOTE: This passes, but with 1E-4 it does not! ⇒ The difference is pretty large!
    assert mamountOut_single == D(mamountOut_double).approxed(abs=D('1E-3'))

# Internal test for invariant changes:
@settings(max_examples=1_000)
@given(
    params=gen_params(),
    balances=gen_balances(),
    amountIn=qdecimals(min_value=1, max_value=1_000_000_000, places=4),
    tokenInIsToken0=st.booleans(),
)
def test_invariant_across_calcOutGivenIn(
    params, balances, amountIn, tokenInIsToken0
):
    ixIn = 0 if tokenInIsToken0 else 1
    ixOut = 1 - ixIn

    # quantized_decimal.set_decimals(18 * 2)

    mparams = params2MathParams(params)
    derived = mathParams2DerivedParams(params2MathParams(params))
    cemm = mimpl.CEMM.from_x_y(balances[0], balances[1], mparams)
    invariant_before = cemm.r
    f_trade = cemm.trade_x if tokenInIsToken0 else cemm.trade_y

    fees = MIN_FEE * amountIn
    amountIn -= fees

    mamountOut = f_trade(amountIn)  # This changes the state of the cemm but whatever

    assume(mamountOut is not None)

    assume(
        balances[0] >= balances[1] * MIN_BALANCE_RATIO and
        balances[1] >= balances[0] * MIN_BALANCE_RATIO
    )

    amountOut = -mamountOut

    new_balances = list(balances)
    new_balances[ixIn] += amountIn + fees
    new_balances[ixOut] -= amountOut

    assume(
        new_balances[0] >= new_balances[1] * MIN_BALANCE_RATIO and
        new_balances[1] >= new_balances[0] * MIN_BALANCE_RATIO
    )

    cemm = mimpl.CEMM.from_x_y(new_balances[0], new_balances[1], mparams)
    invariant_after = cemm.r

    # Losses can be negative or positive; negative means an actual loss.
    losses = calculate_loss(invariant_after - invariant_before, invariant_before, balances)
    loss_ub = -mparams.beta * losses[0] - losses[1]
    max_loss = D('1E-2')
    assert loss_ub <= max_loss

    global error_values
    error_values.append(loss_ub)

    # We need to approx this to 1e-18 at least, not to create an unfair comparison for higher precision.
    # abserr = D('1E-18')
    # assert invariant_after.approxed(abs=abserr) >= invariant_before.approxed(abs=abserr)

### Float version ###

def mparams2float(params: mimpl.Params) -> mimpl_float.Params:
    return mimpl_float.Params(*map(float, (params.alpha, params.beta, params.rx, params.ry, params.l)))

@settings(max_examples=1_000)
@given(
    params=gen_params(),
    balances=gen_balances(),
    amountIn=qdecimals(min_value=1, max_value=1_000_000_000, places=4),
    tokenInIsToken0=st.booleans(),
)
@example(
    params=CEMMMathParams(alpha=D('0.050000000000000000'), beta=D('1.005000000000000000'), c=D('0.984807753012208020'), s=D('0.173648177666930331'), l=D('1.000000000000000000')),
    balances=(2, 1),
    amountIn=D('1.000000000000000000'),
    tokenInIsToken0=False,
)
def test_invariant_across_calcOutGivenIn_float(
    params, balances, amountIn, tokenInIsToken0
):
    ixIn = 0 if tokenInIsToken0 else 1
    ixOut = 1 - ixIn

    balances = tuple(map(float, balances))
    amountIn = float(amountIn)

    mparams = mparams2float(params2MathParams(params))
    cemm = mimpl_float.CEMM.from_x_y(balances[0], balances[1], mparams)
    invariant_before = cemm.r
    f_trade = cemm.trade_x if tokenInIsToken0 else cemm.trade_y

    fees = float(MIN_FEE) * amountIn
    amountIn -= fees

    mamountOut = f_trade(amountIn)  # This changes the state of the cemm but whatever

    assume(mamountOut is not None)

    assume(
        balances[0] >= balances[1] * float(MIN_BALANCE_RATIO) and
        balances[1] >= balances[0] * float(MIN_BALANCE_RATIO)
    )

    amountOut = -mamountOut

    new_balances = list(balances)
    new_balances[ixIn] += amountIn + fees
    new_balances[ixOut] -= amountOut

    assume(
        new_balances[0] >= new_balances[1] * float(MIN_BALANCE_RATIO) and
        new_balances[1] >= new_balances[0] * float(MIN_BALANCE_RATIO)
    )

    cemm = mimpl_float.CEMM.from_x_y(new_balances[0], new_balances[1], mparams)
    invariant_after = cemm.r

    losses = calculate_loss(invariant_after - invariant_before, invariant_after, new_balances)
    loss_ub = -mparams.beta * losses[0] - losses[1]
    max_loss = float('1E-2')
    assert loss_ub <= max_loss

    # We need to approx this to 1e-18 at least, not to create an unfair comparison for higher precision.
    # abserr = float('1E-18')
    # assert invariant_after.approxed(abs=abserr) >= invariant_before.approxed(abs=abserr)

@given(x=st.booleans())
def test_dummy_fails(x):
    assert x


### Main, when used without pytest ###

from contextlib import contextmanager

@contextmanager
def debug(use_pdb=True):
    """When use_pdb is True, enter the debugger if an exception is raised."""
    try:
        yield
    except Exception as e:
        if not use_pdb:
            raise
        import sys
        import traceback
        import pdb
        info = sys.exc_info()
        traceback.print_exception(*info)
        pdb.post_mortem(info[2])

if __name__ == "__main__":
    # When run directly, run this with python from the `vaults/` toplevel dir.
    # (also works with pytest, then this is ignored)
    with debug():
        error_values = []
        test_invariant_across_calcOutGivenIn()
        df = pd.DataFrame({'error': list(map(float, error_values))})
        df.to_feather("data/errors_single_decimal.feather")
