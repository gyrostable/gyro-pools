# Comparison tests comparing the formulas we use for the SOR integration to approximate values of what they
# represent coming from Solidity, for the 2-CLP.
#
# The SOR code itself is typescript and is in another repo.
#
# Note that these are *very* approximate and really only serve to check that our formulas are not total nonsense.
# The bounds of the assertion checks are rather generous and we did not make an effort to make them as tight as
# possible, and neither did we put particular effort to make the approximation of derivatives very precise.
# If these tests fail, it may well be b/c of numerical issues in the "ground truth" that we're testing against, rather
# than the SOR formulas. (note that we're computing the ground truth in fixed point, too, so we import its issues. This
# is not a problem in reality b/c these comparison calculations are not performed in production, only in these tests)

from brownie.test import given
from hypothesis import assume, example

from tests.support.util_common import gen_balances, BasicPoolParameters
from tests.support.utils import scale, unscale, to_decimal, qdecimals
from tests.g2clp.test_two_pool_properties import gen_params
import hypothesis.strategies as st

D = to_decimal

bpool_params = BasicPoolParameters(
    min_price_separation=None,
    max_in_ratio=None,
    max_out_ratio=None,
    min_balance_ratio=D(
        "0.001"
    ),  # Avoid hyper unbalanced pools. (only problematic for normalizedLiquidity)
    min_fee=None,
)

N_ASSETS = 2


def gen_fee():
    return qdecimals(D(0), D("0.1"))


def get_mogrify_values(gyro_two_math_testing, balances, params, ix_in):
    """Calculate dependent values and transform them for easier use to avoid code duplication.

    Returns: l, balances (in, out), virtual params (in, out). All unscaled."""
    ix_out = 1 - ix_in
    sqrt_alpha, sqrt_beta = params
    l = unscale(
        gyro_two_math_testing.calculateInvariant(scale(balances), *scale(params))
    )
    balances_inout = [balances[i] for i in (ix_in, ix_out)]
    virtual_params = unscale(
        [
            gyro_two_math_testing.calculateVirtualParameter0(
                scale(l), scale(sqrt_beta)
            ),
            gyro_two_math_testing.calculateVirtualParameter1(
                scale(l), scale(sqrt_alpha)
            ),
        ]
    )
    virtual_params_inout = [virtual_params[i] for i in (ix_in, ix_out)]
    return l, balances_inout, virtual_params_inout


@given(
    balances=gen_balances(N_ASSETS, bpool_params),
    params=gen_params(),
    fee=gen_fee(),
    ix_in=st.integers(0, 1),
)
def test_p(gyro_two_math_testing, balances, params, fee, ix_in):
    """
    Price of the out-asset in terms of the in-asset
    """
    assume(all(b >= 1 for b in balances))  # Avoid *very* extreme value combinations

    # Transition to in/out instead of 0/1.
    l, balances, virtual_params = get_mogrify_values(
        gyro_two_math_testing, balances, params, ix_in
    )

    amount_out = balances[1] * D("0.001")
    assume(amount_out != 0)

    # Solidity approximation
    amount_in = unscale(
        gyro_two_math_testing.calcInGivenOut(
            *scale(balances),
            scale(amount_out),
            *scale(virtual_params),
        )
    )
    amount_in_after_fee = amount_in / (1 - fee)
    p_approx_sol = amount_in_after_fee / amount_out

    # Analytical calculation
    p = (
        1
        / (1 - fee)
        * (balances[0] + virtual_params[0])
        / (balances[1] + virtual_params[1])
    )

    assert p == p_approx_sol.approxed(rel=D("1e-3"), abs=D("1e-3"))


@given(
    balances=gen_balances(N_ASSETS, bpool_params),
    params=gen_params(),
    fee=gen_fee(),
    ix_in=st.integers(0, 1),
)
def test_dp_d_swapExactIn(gyro_two_math_testing, balances, params, fee, ix_in):
    """
    Derivative of the spot price of the out-asset ito the in-asset as a fct of the in-asset at 0.
    """
    # Transition to in/out instead of 0/1.
    assume(all(b >= 1 for b in balances))  # Avoid *very* extreme value combinations
    ix_out = 1 - ix_in

    balances0 = balances
    l, balances, virtual_params = get_mogrify_values(
        gyro_two_math_testing, balances, params, ix_in
    )

    # Max = how much of the in-asset do I need to put in to take all of the out-asset out.
    amount_in_max = unscale(
        gyro_two_math_testing.calcInGivenOut(
            *scale(balances), scale(balances[1]), *scale(virtual_params)
        )
    )

    # NB this doesn't quite go to amount_in_max when fee > 0. Could be more clever here but meh.
    amount_in = min(amount_in_max, balances[0] * D("0.001"))
    amount_in_after_fee = amount_in * (1 - fee)

    amount_out = unscale(
        gyro_two_math_testing.calcOutGivenIn(
            *scale(balances),
            scale(amount_in_after_fee),
            *scale(virtual_params),
        )
    )

    # Solidity approximation. We calculate two prices analytically (see above test for why this is ok) and
    # approximate the function of the in-asset.

    # First price before the trade
    p0 = (
        1
        / (1 - fee)
        * (balances[0] + virtual_params[0])
        / (balances[1] + virtual_params[1])
    )

    # For the second point, we do *not* put the fees into the pool (this is intentional!), so l and virtual_params
    # don't change.
    p1 = (
        1
        / (1 - fee)
        * (balances[0] + amount_in_after_fee + virtual_params[0])
        / (balances[1] - amount_out + virtual_params[1])
    )

    derivative_approx_sol = (p1 - p0) / amount_in

    derivative_anl = 2 / (balances[1] + virtual_params[1])

    assert derivative_anl == derivative_approx_sol.approxed(
        rel=D("1e-3"), abs=D("1e-3")
    )


@given(
    balances=gen_balances(N_ASSETS, bpool_params),
    params=gen_params(),
    fee=gen_fee(),
    # fee=st.just(D(0)),
    ix_in=st.integers(0, 1),
)
@example(balances=[1000, 1000], params=(D("0.5"), D("1.5")), fee=D("0.1"), ix_in=0)
def test_dp_d_swapExactOut(gyro_two_math_testing, balances, params, fee, ix_in):
    """
    Derivative of the spot price of the out-asset ito the in-asset as a fct of the out-asset at 0.
    """
    # Transition to in/out instead of 0/1.
    assume(all(b >= 1 for b in balances))  # Avoid *very* extreme value combinations
    ix_out = 1 - ix_in

    balances0 = balances
    l, balances, virtual_params = get_mogrify_values(
        gyro_two_math_testing, balances, params, ix_in
    )

    amount_out = min(1, balances[1] * D("0.0001"))

    amount_in = unscale(
        gyro_two_math_testing.calcInGivenOut(
            *scale(balances),
            scale(amount_out),
            *scale(virtual_params),
        )
    )
    # amount_in_after_fee = amount_in / (1 - fee)  # Unused, see below

    # Solidity approximation. We calculate two prices analytically (see above test for why this is ok) and
    # approximate the function of the in-asset.

    # First price before the trade
    p0 = (
        1
        / (1 - fee)
        * (balances[0] + virtual_params[0])
        / (balances[1] + virtual_params[1])
    )

    # For the second point, we do *not* put the fees into the pool (this is intentional!), so l and virtual_params
    # don't change.
    p1 = (
        1
        / (1 - fee)
        * (balances[0] + amount_in + virtual_params[0])
        / (balances[1] - amount_out + virtual_params[1])
    )

    derivative_approx_sol = (p1 - p0) / amount_out

    # Analytical version
    # derivative_anl = (
    #     (1 / (1 - fee))
    #     * 2
    #     * (balances[0] + virtual_params[0])
    #     / (balances[1] + virtual_params[1])**D(2)
    # )
    # Alternative where we compare to the derivative in the middle between the two points instead of at 0.
    # To see that this is the right formula, use the invariant property.
    derivative_anl = (
        (1 / (1 - fee))
        * 2
        * (balances[0] + virtual_params[0])
        * (balances[1] + virtual_params[1])
        / (balances[1] - amount_out / D(2) + virtual_params[1]) ** D(3)
    )

    assert derivative_anl == derivative_approx_sol.approxed(
        rel=D("1e-3"), abs=D("1e-3")
    )


@given(
    balances=gen_balances(N_ASSETS, bpool_params),
    params=gen_params(),
    # fee=gen_fee(),
    fee=st.just(D(0)),
    ix_in=st.integers(0, 1),
)
@example(balances=[1000, 1000], params=(D("0.5"), D("1.5")), fee=D("0.1"), ix_in=0)
def test_normalizedLiquidity(gyro_two_math_testing, balances, params, fee, ix_in):
    """
    Normalized liquidity = 0.5 * 1 / (derivative of the effective (i.e., average) price of the out-asset ito. the in-asset as a fct of the in-amount in the limit at 0).
    """
    assume(all(b >= 1 for b in balances))  # Avoid *very* extreme value combinations
    ix_out = 1 - ix_in

    balances0 = balances
    l, balances, virtual_params = get_mogrify_values(
        gyro_two_math_testing, balances, params, ix_in
    )

    # Make params equivalent if we were to flip everything such that ix_in = 1. Then the price of the out-asset ito. the
    # in-asset = the price of x ito y, like we do in our theory.
    if ix_in == 0:
        params = [D(1) / params[1], D(1) / params[0]]
    bounds = [p ** D(2) for p in params]

    # Solidity approximation of the derivative. Note that the quotient is ill-defined *at* 0, so we take two trade sizes close to 0.
    # Max = how much of the in-asset do I need to put in to take all of the out-asset out.
    amount_in_max = unscale(
        gyro_two_math_testing.calcInGivenOut(
            *scale(balances), scale(balances[1]), *scale(virtual_params)
        )
    )

    # NB this doesn't quite go to amount_in_max when fee > 0. Could be more clever here but meh.
    # NB This shouldn't be too small either b/c then we run into trouble with fixed-point calcs.
    amount_in1 = min(amount_in_max * D("0.999"), balances[0] * D("0.001"))
    amount_in2 = amount_in1 * D("0.99")
    amount_in1_after_fee = amount_in1 * (1 - fee)
    amount_in2_after_fee = amount_in2 * (1 - fee)

    amount_out1 = unscale(
        gyro_two_math_testing.calcOutGivenIn(
            *scale(balances),
            scale(amount_in1_after_fee),
            *scale(virtual_params),
        )
    )
    amount_out2 = unscale(
        gyro_two_math_testing.calcOutGivenIn(
            *scale(balances),
            scale(amount_in2_after_fee),
            *scale(virtual_params),
        )
    )

    p_eff1 = amount_in1 / amount_out1
    p_eff2 = amount_in2 / amount_out2

    assert p_eff1 >= bounds[0] and p_eff2 >= bounds[0]
    assert p_eff2 <= p_eff1

    # These are actually guaranteed. If they're not satisfied, this means that numerical error has a huge influence.
    # I've observed this a few times for this test if we don't have this `assume` and the pool is extremely unbalanced.
    # Note that if this is violated, the higher prices are in the pool's favor, so this is not dangerous per se.
    assume(p_eff1 <= bounds[1] and p_eff2 <= bounds[1])

    d_p_eff_approxed_solidity = (p_eff1 - p_eff2) / (amount_in1 - amount_in2)
    nliq_approxed_solidity = D("0.5") / d_p_eff_approxed_solidity

    # Analytical solution. (yes, it's no more complicated than this!)
    nliq_anl = D("0.5") * (balances[1] + virtual_params[1])

    assert nliq_anl == nliq_approxed_solidity.approxed(rel=D("1e-2"), abs=D("1e-2"))
