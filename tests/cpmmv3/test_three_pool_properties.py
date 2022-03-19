from typing import Tuple

import hypothesis.strategies as st
from brownie.test import given
from brownie import reverts
from hypothesis import assume, settings, example, HealthCheck
import tests.cpmmv3.v3_math_implementation as math_implementation
from tests.cpmmv3.util import calculateInvariantUnderOver, gen_synthetic_balances
from tests.support.util_common import BasicPoolParameters
from tests.support.utils import scale, to_decimal, qdecimals, unscale

from tests.support.quantized_decimal import QuantizedDecimal as D
Decimal = D

billion_balance_strategy = st.integers(min_value=0, max_value=100_000_000_000)

ROOT_ALPHA_MAX = "0.99996666555"
ROOT_ALPHA_MIN = "0.2"
MIN_BAL_RATIO = to_decimal("1e-5")
MIN_FEE = D("0.0002")

bpool_params = BasicPoolParameters(
    D(ROOT_ALPHA_MAX)**3 - 1/D(ROOT_ALPHA_MIN)**3,
    D("0.3"), D("0.3"),
    MIN_BAL_RATIO,
    MIN_FEE
)

def gen_balances_raw():
    return st.tuples(
        billion_balance_strategy, billion_balance_strategy, billion_balance_strategy
    )


@st.composite
def gen_balances(draw):
    balances = draw(gen_balances_raw())
    assume(balances[0] > 0 and balances[1] > 0 and balances[2] > 0)
    if balances[0] > 0:
        assume(min(balances[1], balances[2]) / balances[0] > MIN_BAL_RATIO)
    if balances[1] > 0:
        assume(min(balances[2], balances[0]) / balances[1] > MIN_BAL_RATIO)
    if balances[2] > 0:
        assume(min(balances[0], balances[1]) / balances[2] > MIN_BAL_RATIO)
    return balances


@st.composite
def gen_params_in_given_out(draw):
    balances = draw(gen_balances())
    amount_out = draw(qdecimals("0", to_decimal(balances[1])))
    return balances, amount_out


@st.composite
def gen_params_out_given_in(draw):
    balances = draw(gen_balances())
    amount_in = draw(qdecimals("0", to_decimal(balances[0])))
    return balances, amount_in


def gen_bounds():
    return st.decimals(min_value=ROOT_ALPHA_MIN, max_value=ROOT_ALPHA_MAX, places=4)


###############################################################################################
# Test calculateInvariant is an underestimate
@given(
    balances=gen_balances(),
    root_three_alpha=gen_bounds(),
)
def test_invariant_sol_inv_below_py_inv(
    gyro_three_math_testing, balances, root_three_alpha
):
    mtest_invariant_sol_inv_below_py_inv(
        gyro_three_math_testing, balances, root_three_alpha
    )


# @settings(max_examples=1_000)
@given(
    balances=gen_balances(),
    root_three_alpha=gen_bounds(),
)
@example(balances=(D('1e10'), D(0), D(0)), root_three_alpha=D(ROOT_ALPHA_MAX))
# Same thing:
# @example(balances=(10_000_000_000, 0, 0), root_three_alpha=D(ROOT_ALPHA_MAX).raw)
def test_sol_invariant_underestimated(
    gyro_three_math_testing, balances, root_three_alpha
):
    mtest_sol_invariant_underestimated(
        gyro_three_math_testing, balances, root_three_alpha
    )


###############################################################################################
# test calcInGivenOut for invariant change


# @settings(max_examples=1_000)
@given(
    setup=gen_params_in_given_out(),
    root_three_alpha=st.decimals(
        min_value=ROOT_ALPHA_MIN, max_value=ROOT_ALPHA_MAX, places=4
    ),
)
def test_invariant_across_calcInGivenOut(
    gyro_three_math_testing,
    root_three_alpha,
    setup,
):
    balances, amount_out = setup
    invariant_after, invariant = mtest_invariant_across_calcInGivenOut(
        gyro_three_math_testing, balances, amount_out, root_three_alpha, False
    )
    assert invariant_after >= invariant


###############################################################################################
# test calcOutGivenIn for invariant change


# @settings(max_examples=1_000)
@given(
    setup=gen_params_out_given_in(),
    root_three_alpha=st.decimals(
        min_value=ROOT_ALPHA_MIN, max_value=ROOT_ALPHA_MAX, places=4
    ),
)
def test_invariant_across_calcOutGivenIn(
    gyro_three_math_testing, root_three_alpha, setup
):
    balances, amount_in = setup

    invariant_after, invariant = mtest_invariant_across_calcOutGivenIn(
        gyro_three_math_testing, balances, amount_in, root_three_alpha, False
    )
    assert invariant_after >= invariant


###############################################################################################
# mtest functions


def mtest_invariant_sol_inv_below_py_inv(
    gyro_three_math_testing, balances: Tuple[int, int, int], root_three_alpha
):
    invariant = math_implementation.calculateInvariant(
        to_decimal(balances), to_decimal(root_three_alpha)
    )

    invariant_sol_under, _ = calculateInvariantUnderOver(gyro_three_math_testing,
        scale(balances), scale(root_three_alpha)
    )

    assert unscale(D(invariant_sol_under)) <= invariant


def mtest_sol_invariant_underestimated(
    gyro_three_math_testing, balances: Tuple[int, int, int], root_three_alpha
):
    # TODO Perhaps remove this test. It's a bit trivial now since we also check underestimation in solidity.
    (a, mb, mc, md) = math_implementation.calculateCubicTerms(
        to_decimal(balances), to_decimal(root_three_alpha)
    )
    (b, c, d) = (-mb, -mc, -md)
    L, _ = unscale(
        calculateInvariantUnderOver(gyro_three_math_testing,
            scale(balances), scale(root_three_alpha)
        )
    )
    # f_L_float = calculate_f_L_float(L, balances, root_three_alpha)
    # f_L_prime_float = calculate_f_L_prime_float(L, balances, root_three_alpha)
    f_L_decimal = calculate_f_L_decimal(L, a, b, c, d)
    # assert f_L_float + f_L_prime_float * 1e-18 <= 0
    assert f_L_decimal <= 0


def calculate_cubic_terms_float(balances: Tuple[int, int, int], root_three_alpha: D):
    x, y, z = balances
    x, y, z = (float(x), float(y), float(z))
    root_three_alpha = float(root_three_alpha)
    a = 1 - root_three_alpha ** 3
    b = -(x + y + z) * root_three_alpha ** 2
    c = -(x * y + y * z + x * z) * root_three_alpha
    d = -x * y * z
    return a, b, c, d


def calculate_f_L_float(L: D, balances: Tuple[int, int, int], root_three_alpha: D):
    a, b, c, d = calculate_cubic_terms_float(balances, root_three_alpha)
    L = float(L)
    return L ** 3 * a + L ** 2 * b + L * c + d


def calculate_f_L_prime_float(
    L: D, balances: Tuple[int, int, int], root_three_alpha: D
):
    a, b, c, d = calculate_cubic_terms_float(balances, root_three_alpha)
    L = float(L)
    return L ** 2 * a * 3 + L * b * 2 + c


def calculate_f_L_decimal(L: D, a: D, b: D, c: D, d: D):
    return L.mul_up(L).mul_up(L).mul_up(a) + L * L * b + L * c + d


def mtest_invariant_across_calcInGivenOut(
    gyro_three_math_testing, balances, amount_out, root_three_alpha, check_sol_inv
):
    assume(amount_out < to_decimal("0.3") * (balances[1]))

    invariant = math_implementation.calculateInvariant(
        to_decimal(balances), to_decimal(root_three_alpha)
    )

    invariant_sol_under, invariant_sol_over = unscale(calculateInvariantUnderOver(gyro_three_math_testing,
        scale(balances), scale(root_three_alpha)
    ))

    assert invariant_sol_under <= invariant.approxed(abs=D('5e-18'))
    assert invariant <= invariant_sol_over.approxed(abs=D('5e-18'))

    virtual_offset_under = invariant_sol_under * to_decimal(root_three_alpha)
    virtual_offset_over  = invariant_sol_over * to_decimal(root_three_alpha)
    virtual_offset_mid = (virtual_offset_under + virtual_offset_over) / D(2)

    # Q: Should we only use this one here?
    virtual_offset = invariant * to_decimal(root_three_alpha)

    in_amount = math_implementation.calcInGivenOut(
        to_decimal(balances[0]),
        to_decimal(balances[1]),
        to_decimal(amount_out),
        virtual_offset_mid,
    )

    bal_out_new, bal_in_new = (balances[0] + in_amount, balances[1] - amount_out)
    if bal_out_new > bal_in_new:
        within_bal_ratio = bal_in_new / bal_out_new > MIN_BAL_RATIO
    else:
        within_bal_ratio = bal_out_new / bal_in_new > MIN_BAL_RATIO

    if in_amount <= to_decimal("0.3") * balances[0] and within_bal_ratio:
        in_amount_sol = unscale(gyro_three_math_testing.calcInGivenOut(
            scale(balances[0]),
            scale(balances[1]),
            scale(amount_out),
            scale(virtual_offset_under),
            scale(virtual_offset_over)
        ))
    elif not within_bal_ratio:
        with reverts("BAL#357"):  # MIN_BAL_RATIO
            gyro_three_math_testing.calcInGivenOut(
                scale(balances[0]),
                scale(balances[1]),
                scale(amount_out),
                scale(virtual_offset_under),
                scale(virtual_offset_over)
            )
        return 0, 0
    else:
        with reverts("BAL#304"):  # MAX_IN_RATIO
            gyro_three_math_testing.calcInGivenOut(
                scale(balances[0]),
                scale(balances[1]),
                scale(amount_out),
                scale(virtual_offset_under),
                scale(virtual_offset_over)
            )
        return 0, 0

    # Sanity check. Note that the two values use slightly different invariants, so they're not gonna be equal!
    assert to_decimal(in_amount_sol) == in_amount.approxed()

    balances_after = balances_after = (
        balances[0] + in_amount / (1 - MIN_FEE),
        balances[1] - amount_out,
        balances[2],
    )

    invariant_after = math_implementation.calculateInvariant(
        to_decimal(balances_after), to_decimal(root_three_alpha)
    )

    if check_sol_inv:
        invariant_sol_after_under, invariant_sol_after_over = calculateInvariantUnderOver(gyro_three_math_testing,
            scale(balances_after), scale(root_three_alpha)
        )

        assert unscale(invariant_sol_after_over) >= invariant_sol_under  # TODO should this be `invariant` or so??

    # return invariant_after, invariant
    partial_invariant_from_offsets = calculate_partial_invariant_from_offsets(
        balances, virtual_offset
    )
    partial_invariant_from_offsets_after = calculate_partial_invariant_from_offsets(
        balances_after, virtual_offset
    )
    partial_invariant_from_sol = invariant_sol_under / (D(balances[2]) + D(virtual_offset))
    assert partial_invariant_from_offsets >= partial_invariant_from_sol
    # assert invariant_from_offsets >= invariant_sol
    return partial_invariant_from_offsets_after, partial_invariant_from_offsets


def mtest_invariant_across_calcOutGivenIn(
    gyro_three_math_testing, balances, amount_in, root_three_alpha, check_sol_inv
):
    assume(amount_in < to_decimal("0.3") * (balances[0]))

    fees = MIN_FEE * amount_in
    amount_in -= fees

    invariant = math_implementation.calculateInvariant(
        to_decimal(balances), to_decimal(root_three_alpha)
    )
    invariant_sol, is_underestimate = gyro_three_math_testing.underestimateInvariant(
        scale(balances), scale(root_three_alpha)
    )
    invariant_sol = unscale(invariant_sol)
    assert is_underestimate

    virtual_offset = invariant_sol * to_decimal(root_three_alpha)

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
        return 0, 0
    elif not within_bal_ratio:
        with reverts("BAL#357"):  # MIN_BAL_RATIO
            gyro_three_math_testing.calcOutGivenIn(
                scale(balances[0]),
                scale(balances[1]),
                scale(amount_in),
                scale(virtual_offset),
            )
        return 0, 0
    else:
        with reverts("BAL#305"):  # MAX_OUT_RATIO
            gyro_three_math_testing.calcOutGivenIn(
                scale(balances[0]),
                scale(balances[1]),
                scale(amount_in),
                scale(virtual_offset),
            )
        return 0, 0

    assert to_decimal(out_amount_sol) == scale(out_amount)

    balances_after = (
        balances[0] + amount_in + fees,
        balances[1] - unscale(out_amount_sol),
        balances[2],
    )
    invariant_after = math_implementation.calculateInvariant(
        to_decimal(balances_after), to_decimal(root_three_alpha)
    )

    if check_sol_inv:
        invariant_sol_after_under, invariant_sol_after_over = calculateInvariantUnderOver(gyro_three_math_testing,
            scale(balances_after), scale(root_three_alpha)
        )

    # assert invariant_after >= invariant
    if check_sol_inv:
        assert unscale(invariant_sol_after_over) >= invariant_sol

    # return invariant_after, invariant
    partial_invariant_from_offsets = calculate_partial_invariant_from_offsets(
        balances, virtual_offset
    )
    partial_invariant_from_offsets_after = calculate_partial_invariant_from_offsets(
        balances_after, virtual_offset
    )
    partial_invariant_from_sol = invariant_sol / (D(balances[2]) + D(virtual_offset))
    assert partial_invariant_from_offsets >= partial_invariant_from_sol
    # assert invariant_from_offsets >= invariant_sol
    return partial_invariant_from_offsets_after, partial_invariant_from_offsets


def calculate_invariant_from_offsets(balances, virtual_offset):
    return (
        ((D(balances[0]) + D(virtual_offset)) ** D(1 / 3))
        .mul_up((D(balances[1]) + D(virtual_offset)) ** D(1 / 3))
        .mul_up((D(balances[2]) + D(virtual_offset)) ** D(1 / 3))
    )


def calculate_partial_invariant_from_offsets(balances, virtual_offset):
    # ignores the third balance b/c it is not changed in a swap.
    # this has better fixed point precision b/c the extra factor can otherwise be large
    return (D(balances[0]) + D(virtual_offset)).mul_up(
        D(balances[1] + D(virtual_offset))
    )

@settings(max_examples=1000)
@given(
    args=gen_synthetic_balances(bpool_params, ROOT_ALPHA_MIN, ROOT_ALPHA_MAX, min_balance=D(10)),
)
@example(args=(
    (D('16743757275.452039152786685295'),
     D('1967668306.780847696789534899'),
     D('396788946.610986231634363959')),
    D('3812260336.851356457000000000'),
    D('0.200000000181790486')),
)
@example(args=((Decimal('728109563488.263687529903349137'),
      Decimal('7281095.634882636875299036'),
      Decimal('1724716619.689367265339564601')),
     Decimal('36417643407.707023648100000000'),
     Decimal('0.200000000021982758')))
def test_calculateInvariant_reconstruction(args, gyro_three_math_testing):
    balances, invariant, root3Alpha = args

    invariant_re_under, invariant_re_over = unscale(calculateInvariantUnderOver(gyro_three_math_testing,
        scale(balances),
        scale(root3Alpha)))

    assert invariant_re_under <= invariant.approxed(rel=D('5e-18'))
    assert invariant_re_over  >= invariant.approxed(rel=D('5e-16'))
    # assert invariant_re_under == invariant_re_over.approxed(rel=D('5e-14'))
    assert invariant_re_under == invariant.approxed(abs=D('3e-18'), rel=D('3e-18'))
    assert invariant_re_under == invariant.approxed(abs=D('5e-16'))
    # assert invariant_re_over  == invariant.approxed(rel=D('1e-12'))
