from decimal import Decimal
from typing import Tuple

import hypothesis.strategies as st
import numpy as np
from hypothesis import settings, assume

import tests.cpmmv3.v3_math_implementation as math_implementation
from brownie import reverts
from brownie.test import given
from tests.support.utils import scale, to_decimal, unscale, qdecimals

from tests.support.quantized_decimal import QuantizedDecimal as D

billion_balance_strategy = st.integers(min_value=0, max_value=100_000_000_000)

ROOT_ALPHA_MAX = "0.99996666555"
ROOT_ALPHA_MIN = "0.2"
MIN_BAL_RATIO = to_decimal("1e-5")


def faulty_params(balances, root_three_alpha):
    balances = [to_decimal(b) for b in balances]
    if balances[0] == 0 and balances[1] == 0 and balances[2] == 0:
        return True
    else:
        return False


@given(
    balances=st.tuples(
        billion_balance_strategy, billion_balance_strategy, billion_balance_strategy
    ),
    root_three_alpha=st.decimals(
        min_value=ROOT_ALPHA_MIN, max_value=ROOT_ALPHA_MAX, places=4
    ),
)
def test_calculate_cubic_terms(
    gyro_three_math_testing, balances: Tuple[int, int], root_three_alpha: Decimal
):
    assume(not faulty_params(balances, root_three_alpha))

    (a, mb, mc, md) = math_implementation.calculateCubicTerms(
        to_decimal(balances), to_decimal(root_three_alpha)
    )

    (a_sol, mb_sol, mc_sol, md_sol) = gyro_three_math_testing.calculateCubicTerms(
        scale(balances), scale(root_three_alpha)
    )

    assert a_sol == scale(a)
    assert mb_sol == scale(mb)
    assert mc_sol == scale(mc)
    assert md_sol == scale(md)


# @given(
#     balances=st.tuples(billion_balance_strategy, billion_balance_strategy, billion_balance_strategy),
#     root_three_alpha=st.decimals(min_value="0.02", max_value="0.99995", places=4),
# )
# def test_calculate_quadratic(gyro_three_math_testing, balances, root_three_alpha):
#     if faulty_params(balances, root_three_alpha):
#         return

#     (a, mb, mc) = math_implementation.calculateQuadraticTerms(
#         to_decimal(balances), to_decimal(root_three_alpha)
#     )

#     assert not any(v < 0 for v in [a, mb, mc])

#     root = math_implementation.calculateQuadratic(a, -mb, -mc)

#     root_sol = gyro_three_math_testing.calculateQuadratic(
#         scale(a), scale(mb), scale(mc)
#     )

#     assert int(root_sol) == scale(root).approxed()


def gen_balances_raw():
    return st.tuples(
        billion_balance_strategy, billion_balance_strategy, billion_balance_strategy
    )


@st.composite
def gen_params_in_given_out(draw):
    balances = draw(gen_balances_raw())
    assume(balances[0] > 0 and balances[1] > 0 and balances[2] > 0)
    amount_out = draw(qdecimals("0", to_decimal(balances[1])))
    return balances, amount_out


@st.composite
def gen_params_out_given_in(draw):
    balances = draw(gen_balances_raw())
    assume(balances[0] > 0 and balances[1] > 0 and balances[2] > 0)
    amount_in = draw(qdecimals("0", to_decimal(balances[0])))
    return balances, amount_in


@given(
    setup=gen_params_in_given_out(),
    root_three_alpha=st.decimals(
        min_value=ROOT_ALPHA_MIN, max_value=ROOT_ALPHA_MAX, places=4
    ),
)
def test_calc_in_given_out(
    gyro_three_math_testing,
    root_three_alpha,
    setup,
):
    balances, amount_out = setup

    # assume(not faulty_params)

    assume(amount_out < to_decimal("0.3") * (balances[1]))

    invariant = math_implementation.calculateInvariant(
        to_decimal(balances), to_decimal(root_three_alpha)
    )

    virtual_offset = invariant * to_decimal(root_three_alpha)

    in_amount = math_implementation.calcInGivenOut(
        to_decimal(balances[0]),
        to_decimal(balances[1]),
        to_decimal(amount_out),
        virtual_offset,
    )

    bal_out_new, bal_in_new = (balances[0] + in_amount, balances[1] - amount_out)
    if bal_out_new > bal_in_new:
        within_bal_ratio = bal_in_new / bal_out_new > MIN_BAL_RATIO
    else:
        within_bal_ratio = bal_out_new / bal_in_new > MIN_BAL_RATIO

    if in_amount <= to_decimal("0.3") * balances[0] and within_bal_ratio:
        in_amount_sol = gyro_three_math_testing.calcInGivenOut(
            scale(balances[0]),
            scale(balances[1]),
            scale(amount_out),
            scale(virtual_offset),
        )
    elif not within_bal_ratio:
        with reverts("BAL#357"):  # MIN_BAL_RATIO
            gyro_three_math_testing.calcInGivenOut(
                scale(balances[0]),
                scale(balances[1]),
                scale(amount_out),
                scale(virtual_offset),
            )
        return
    else:
        with reverts("BAL#304"):  # MAX_IN_RATIO
            gyro_three_math_testing.calcInGivenOut(
                scale(balances[0]),
                scale(balances[1]),
                scale(amount_out),
                scale(virtual_offset),
            )
        return

    assert to_decimal(in_amount_sol) == scale(in_amount)


@given(
    setup=gen_params_out_given_in(),
    root_three_alpha=st.decimals(
        min_value=ROOT_ALPHA_MIN, max_value=ROOT_ALPHA_MAX, places=4
    ),
)
def test_calc_out_given_in(gyro_three_math_testing, root_three_alpha, setup):
    balances, amount_in = setup

    # assume(not faulty_params)
    assume(amount_in < to_decimal("0.3") * (balances[0]))

    invariant = math_implementation.calculateInvariant(
        to_decimal(balances), to_decimal(root_three_alpha)
    )

    virtual_offset = invariant * to_decimal(root_three_alpha)

    out_amount = math_implementation.calcOutGivenIn(
        to_decimal(balances[0]),
        to_decimal(balances[1]),
        to_decimal(amount_in),
        virtual_offset,
    )

    bal_out_new, bal_in_new = (balances[0] + amount_in, balances[1] - out_amount)
    if bal_out_new > bal_in_new:
        within_bal_ratio = bal_in_new / bal_out_new > MIN_BAL_RATIO
    else:
        within_bal_ratio = bal_out_new / bal_in_new > MIN_BAL_RATIO

    if (
        out_amount <= to_decimal("0.3") * balances[1]
        and within_bal_ratio
        and out_amount >= 0
    ):
        out_amount_sol = gyro_three_math_testing.calcOutGivenIn(
            scale(balances[0]),
            scale(balances[1]),
            scale(amount_in),
            scale(virtual_offset),
        )
    elif out_amount < 0:
        with reverts("BAL#001"):  # subtraction overflow when ~ 0 and rounding down
            gyro_three_math_testing.calcOutGivenIn(
                scale(balances[0]),
                scale(balances[1]),
                scale(amount_in),
                scale(virtual_offset),
            )
        return
    elif not within_bal_ratio:
        with reverts("BAL#357"):  # MIN_BAL_RATIO
            gyro_three_math_testing.calcOutGivenIn(
                scale(balances[0]),
                scale(balances[1]),
                scale(amount_in),
                scale(virtual_offset),
            )
        return
    else:
        with reverts("BAL#305"):  # MAX_OUT_RATIO
            gyro_three_math_testing.calcOutGivenIn(
                scale(balances[0]),
                scale(balances[1]),
                scale(amount_in),
                scale(virtual_offset),
            )
        return

    assert to_decimal(out_amount_sol) == scale(out_amount)


@given(
    balances=st.tuples(
        billion_balance_strategy, billion_balance_strategy, billion_balance_strategy
    ),
    root_three_alpha=st.decimals(min_value="0.9", max_value=ROOT_ALPHA_MAX, places=4),
)
def test_calculate_invariant(
    gyro_three_math_testing, balances: Tuple[int, int, int], root_three_alpha
):

    assume(not faulty_params(balances, root_three_alpha))

    invariant = math_implementation.calculateInvariant(
        to_decimal(balances), to_decimal(root_three_alpha)
    )

    (a, b, c, d) = math_implementation.calculateCubicTerms(
        to_decimal(balances), root_three_alpha
    )

    roots = np.roots([a, -b, -c, -d])

    invariant_sol = gyro_three_math_testing.calculateInvariant(
        scale(balances), scale(root_three_alpha)
    )

    assert int(invariant_sol) == scale(invariant).approxed(rel=D("1e-14"))


# @given(
#     balances=st.tuples(
#         billion_balance_strategy, billion_balance_strategy, billion_balance_strategy
#     ),
#     bpt_amount_out=st.decimals(min_value="1", max_value="1000000", places=4),
#     total_bpt=st.decimals(min_value="1", max_value="1000000", places=4),
# )
# def test_all_tokens_in_given_exact_bpt_out(
#     gyro_three_math_testing, balances: Tuple[int, int, int], bpt_amount_out, total_bpt
# ):

#     if total_bpt < bpt_amount_out:
#         return

#     amounts_in = math_implementation.calcAllTokensInGivenExactBptOut(
#         to_decimal(balances), to_decimal(bpt_amount_out), to_decimal(total_bpt)
#     )

#     amounts_in_sol = gyro_three_math_testing.calcAllTokensInGivenExactBptOut(
#         scale(balances), scale(bpt_amount_out), scale(total_bpt)
#     )

#     if amounts_in_sol[0] == 1 or amounts_in_sol[1] == 1:
#         return

#     assert to_decimal(amounts_in_sol[0]) == scale(amounts_in[0]).approxed()
#     assert to_decimal(amounts_in_sol[1]) == scale(amounts_in[1]).approxed()


# @given(
#     balances=st.tuples(
#         billion_balance_strategy, billion_balance_strategy, billion_balance_strategy
#     ),
#     bpt_amount_in=st.decimals(min_value="1", max_value="1000000", places=4),
#     total_bpt=st.decimals(min_value="1", max_value="1000000", places=4),
# )
# def test_tokens_out_given_exact_bpt_in(
#     gyro_three_math_testing, balances: Tuple[int, int, int], bpt_amount_in, total_bpt
# ):

#     if total_bpt < bpt_amount_in:
#         return

#     amounts_in = math_implementation.calcAllTokensInGivenExactBptOut(
#         to_decimal(balances), to_decimal(bpt_amount_in), to_decimal(total_bpt)
#     )

#     amounts_in_sol = gyro_three_math_testing.calcAllTokensInGivenExactBptOut(
#         scale(balances), scale(bpt_amount_in), scale(total_bpt)
#     )

#     if amounts_in_sol[0] == 1 or amounts_in_sol[1] == 1:
#         return

#     assert to_decimal(amounts_in_sol[0]) == scale(amounts_in[0]).approxed()
#     assert to_decimal(amounts_in_sol[1]) == scale(amounts_in[1]).approxed()


# @given(
#     balances=st.tuples(
#         billion_balance_strategy, billion_balance_strategy, billion_balance_strategy
#     ),
#     delta_balances=st.tuples(
#         billion_balance_strategy, billion_balance_strategy, billion_balance_strategy
#     ),
#     protocol_fee_gyro_portion=st.decimals(min_value="0.00", max_value="0.5", places=4),
#     protocol_swap_fee_percentage=st.decimals(
#         min_value="0.0", max_value="0.4", places=4
#     ),
#     current_bpt_supply=st.decimals(min_value="1", max_value="100000", places=4),
#     root_three_alpha=st.decimals(
#         min_value=ROOT_ALPHA_MIN, max_value=ROOT_ALPHA_MAX, places=4
#     ),
# )
# def test_protocol_fees(
#     gyro_three_math_testing,
#     current_bpt_supply: Decimal,
#     balances: Tuple[int, int, int],
#     delta_balances: Tuple[int, int, int],
#     protocol_swap_fee_percentage,
#     protocol_fee_gyro_portion,
#     root_three_alpha: Decimal,
# ):

#     assume(not faulty_params(balances, root_three_alpha))

#     old_invariant = math_implementation.calculateInvariant(
#         to_decimal(balances), to_decimal(root_three_alpha)
#     )

#     new_balance_0 = balances[0] + delta_balances[0]
#     new_balance_1 = balances[1] + delta_balances[1]
#     new_balance_2 = balances[2] + delta_balances[2]

#     new_balances = (new_balance_0, new_balance_1, new_balance_2)

#     new_invariant = math_implementation.calculateInvariant(
#         to_decimal(new_balances), to_decimal(root_three_alpha)
#     )

#     protocol_fees = math_implementation.calcProtocolFees(
#         to_decimal(old_invariant),
#         to_decimal(new_invariant),
#         to_decimal(current_bpt_supply),
#         to_decimal(protocol_swap_fee_percentage),
#         to_decimal(protocol_fee_gyro_portion),
#     )

#     protocol_fees_sol = gyro_three_math_testing.calcProtocolFees(
#         scale(old_invariant),
#         scale(new_invariant),
#         scale(current_bpt_supply),
#         scale(protocol_swap_fee_percentage),
#         scale(protocol_fee_gyro_portion),
#     )

#     assert to_decimal(protocol_fees_sol[0]) == scale(protocol_fees[0])
#     assert to_decimal(protocol_fees_sol[1]) == scale(protocol_fees[1])
