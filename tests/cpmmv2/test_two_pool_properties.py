from decimal import Decimal
from typing import Tuple

import hypothesis.strategies as st
from brownie.test import given
from brownie import reverts
from hypothesis import assume, settings
from tests.cpmmv2 import math_implementation
from tests.support.utils import scale, to_decimal, qdecimals, unscale

from tests.support.quantized_decimal import QuantizedDecimal as D

billion_balance_strategy = st.integers(min_value=0, max_value=100_000_000_000)

# this is a multiplicative separation
# This is consistent with tightest price range of 0.9999 - 1.0001
MIN_SQRTPARAM_SEPARATION = to_decimal("1.0001")
MIN_BAL_RATIO = to_decimal("1e-5")
MIN_FEE = D("0.0002")


def faulty_params(balances, sqrt_alpha, sqrt_beta):
    balances = [to_decimal(b) for b in balances]
    if balances[0] == 0 and balances[1] == 0:
        return True
    return sqrt_beta <= sqrt_alpha * MIN_SQRTPARAM_SEPARATION


################################################################################
### parameter selection


@st.composite
def gen_params(draw):
    sqrt_alpha = draw(qdecimals("0.05", "19.0"))
    sqrt_beta = draw(qdecimals(sqrt_alpha.raw, "20.0"))
    assume(sqrt_beta.raw - sqrt_alpha.raw >= MIN_SQRTPARAM_SEPARATION)
    return (sqrt_alpha, sqrt_beta)


def gen_balances_raw():
    return st.tuples(billion_balance_strategy, billion_balance_strategy)


@st.composite
def gen_balances(draw):
    balances = draw(gen_balances_raw())
    assume(balances[0] > 0 and balances[1] > 0)
    assume(balances[0] / balances[1] > 1e-5)
    assume(balances[1] / balances[0] > 1e-5)
    return balances


@st.composite
def gen_params_cemm_dinvariant(draw):
    sqrt_alpha, sqrt_beta = draw(gen_params())
    balances = draw(gen_balances())
    assume(balances[0] > 0 and balances[1] > 0)
    invariant = math_implementation.calculateInvariant(balances, sqrt_alpha, sqrt_beta)
    dinvariant = draw(
        qdecimals(-invariant, 2 * invariant)
    )  # Upper bound kinda arbitrary
    assume(abs(dinvariant) > D("1E-10"))  # Only relevant updates
    return sqrt_alpha, sqrt_beta, dinvariant


################################################################################
### test calcInGivenOut for invariant change
# @settings(max_examples=1_000)
@given(
    balances=st.tuples(billion_balance_strategy, billion_balance_strategy),
    amount_out=st.decimals(min_value="1", max_value="1000000", places=4),
    sqrt_alpha=st.decimals(min_value="0.02", max_value="0.99995", places=4),
    sqrt_beta=st.decimals(min_value="1.00005", max_value="1.8", places=4),
)
def test_invariant_across_calcInGivenOut(
    gyro_two_math_testing, amount_out, balances: Tuple[int, int], sqrt_alpha, sqrt_beta
):
    assume(amount_out <= to_decimal("0.3") * (balances[1]))
    assume(balances[0] > 0 and balances[1] > 0)

    assume(not faulty_params(balances, sqrt_alpha, sqrt_beta))

    invariant = math_implementation.calculateInvariant(
        to_decimal(balances), to_decimal(sqrt_alpha), to_decimal(sqrt_beta)
    )

    invariant_sol = gyro_two_math_testing.calculateInvariant(
        scale(balances), scale(sqrt_alpha), scale(sqrt_beta)
    )

    virtual_param_in = math_implementation.calculateVirtualParameter0(
        to_decimal(invariant), to_decimal(sqrt_beta)
    )

    virtual_param_out = math_implementation.calculateVirtualParameter1(
        to_decimal(invariant), to_decimal(sqrt_alpha)
    )

    in_amount = math_implementation.calcInGivenOut(
        to_decimal(balances[0]),
        to_decimal(balances[1]),
        to_decimal(amount_out),
        to_decimal(virtual_param_in),
        to_decimal(virtual_param_out),
        to_decimal(invariant),
    )

    bal_out_new, bal_in_new = (balances[0] + in_amount, balances[1] - amount_out)
    if bal_out_new > bal_in_new:
        within_bal_ratio = bal_in_new / bal_out_new > MIN_BAL_RATIO
    else:
        within_bal_ratio = bal_out_new / bal_in_new > MIN_BAL_RATIO

    if in_amount <= to_decimal("0.3") * balances[0] and within_bal_ratio:
        in_amount_sol = gyro_two_math_testing.calcInGivenOut(
            scale(balances[0]),
            scale(balances[1]),
            scale(amount_out),
            scale(virtual_param_in),
            scale(virtual_param_out),
            scale(invariant),
        )
    elif not within_bal_ratio:
        with reverts("BAL#357"):  # MIN_BAL_RATIO
            gyro_two_math_testing.calcInGivenOut(
                scale(balances[0]),
                scale(balances[1]),
                scale(amount_out),
                scale(virtual_param_in),
                scale(virtual_param_out),
                scale(invariant),
            )
        return
    else:
        with reverts("BAL#304"):  # MAX_IN_RATIO
            gyro_two_math_testing.calcInGivenOut(
                scale(balances[0]),
                scale(balances[1]),
                scale(amount_out),
                scale(virtual_param_in),
                scale(virtual_param_out),
                scale(invariant),
            )
        return

    assert to_decimal(in_amount_sol) >= scale(in_amount)

    balances_after = (
        balances[0] + unscale(in_amount_sol) * (1 + MIN_FEE),
        balances[1] - amount_out,
    )
    invariant_after = math_implementation.calculateInvariant(
        to_decimal(balances_after), to_decimal(sqrt_alpha), to_decimal(sqrt_beta)
    )

    invariant_sol_after = gyro_two_math_testing.calculateInvariant(
        scale(balances_after), scale(sqrt_alpha), scale(sqrt_beta)
    )

    assert invariant_after >= invariant
    assert invariant_sol_after >= invariant_sol


################################################################################
### test calcOutGivenIn for invariant change


@given(
    balances=st.tuples(billion_balance_strategy, billion_balance_strategy),
    amount_in=st.decimals(min_value="1", max_value="1000000", places=4),
    sqrt_alpha=st.decimals(min_value="0.02", max_value="0.99995", places=4),
    sqrt_beta=st.decimals(min_value="1.00005", max_value="1.8", places=4),
)
def test_invariant_across_calcOutGivenIn(
    gyro_two_math_testing, amount_in, balances: Tuple[int, int], sqrt_alpha, sqrt_beta
):
    assume(amount_in <= to_decimal("0.3") * (balances[0]))
    assume(balances[0] > 0 and balances[1] > 0)

    assume(not faulty_params(balances, sqrt_alpha, sqrt_beta))

    fees = MIN_FEE * amount_in
    amount_in -= fees

    invariant = math_implementation.calculateInvariant(
        to_decimal(balances), to_decimal(sqrt_alpha), to_decimal(sqrt_beta)
    )

    invariant_sol = gyro_two_math_testing.calculateInvariant(
        scale(balances), scale(sqrt_alpha), scale(sqrt_beta)
    )

    virtual_param_in = math_implementation.calculateVirtualParameter0(
        to_decimal(invariant), to_decimal(sqrt_beta)
    )

    virtual_param_out = math_implementation.calculateVirtualParameter1(
        to_decimal(invariant), to_decimal(sqrt_alpha)
    )

    out_amount = math_implementation.calcOutGivenIn(
        to_decimal(balances[0]),
        to_decimal(balances[1]),
        to_decimal(amount_in),
        to_decimal(virtual_param_in),
        to_decimal(virtual_param_out),
        to_decimal(invariant),
    )

    bal_out_new, bal_in_new = (balances[0] + amount_in, balances[1] - out_amount)
    if bal_out_new > bal_in_new:
        within_bal_ratio = bal_in_new / bal_out_new > MIN_BAL_RATIO
    else:
        within_bal_ratio = bal_out_new / bal_in_new > MIN_BAL_RATIO

    if out_amount <= to_decimal("0.3") * balances[1] and within_bal_ratio:
        out_amount_sol = gyro_two_math_testing.calcOutGivenIn(
            scale(balances[0]),
            scale(balances[1]),
            scale(amount_in),
            scale(virtual_param_in),
            scale(virtual_param_out),
            scale(invariant),
        )
    elif not within_bal_ratio:
        with reverts("BAL#357"):  # MIN_BAL_RATIO
            gyro_two_math_testing.calcOutGivenIn(
                scale(balances[0]),
                scale(balances[1]),
                scale(amount_in),
                scale(virtual_param_in),
                scale(virtual_param_out),
                scale(invariant),
            )
        return
    else:
        with reverts("BAL#305"):  # MAX_OUT_RATIO
            gyro_two_math_testing.calcOutGivenIn(
                scale(balances[0]),
                scale(balances[1]),
                scale(amount_in),
                scale(virtual_param_in),
                scale(virtual_param_out),
                scale(invariant),
            )
        return

    assert to_decimal(out_amount_sol) <= scale(out_amount)

    balances_after = (
        balances[0] + amount_in + fees,
        balances[1] - unscale(out_amount_sol),
    )
    invariant_after = math_implementation.calculateInvariant(
        to_decimal(balances_after), to_decimal(sqrt_alpha), to_decimal(sqrt_beta)
    )

    invariant_sol_after = gyro_two_math_testing.calculateInvariant(
        scale(balances_after), scale(sqrt_alpha), scale(sqrt_beta)
    )

    assert invariant_after >= invariant
    assert invariant_sol_after >= invariant_sol


################################################################################
### test liquidity invariant update for invariant change
