from typing import Callable

from hypothesis import assume

from tests.support.util_common import BasicPoolParameters
from tests.support.quantized_decimal import QuantizedDecimal as D

import hypothesis.strategies as st

from tests.support.utils import qdecimals


def calculateInvariantUnderOver(gyro_three_math_testing, balances, root3Alpha):
    """Use like gyro_three_math_testing; we assert that we actually get an underestimate. No scaling is done."""
    # Calling as transaction to get more debug info, and for gas estimation.
    # For example: run `brownie test` with `-I` and look at `history[-1].call_trace()`.
    # Default off for speed (not sure how much of a difference this actually makes)
    # tx = gyro_three_math_testing.calculateInvariantUnderOver.transact(balances, root3Alpha)
    # l_under, under_is_under, l_over = tx.return_value
    l_under, under_is_under, l_over = gyro_three_math_testing.calculateInvariantUnderOver(balances, root3Alpha)
    assert under_is_under
    return l_under, l_over


@st.composite
def gen_feasible_prices(draw: Callable, alpha: D):
    # NOTE: This is really slow, though I also don't know how we might possibly speed it up.
    # You likely need `@settings(suppress_health_check=[HealthCheck.too_slow])` in your tests.
    """Generate relative prices p_x/z and p_y/z that are 'fesible' in the sense of Prop. 9."""
    px = draw(qdecimals(alpha, D(1)/alpha))

    # We ensure the "x >= 0" and "y >= 0" properties by choice of py's bounds.
    # This is important for test performance.
    # "z >= 0" needs to be additionally assumed.
    py = draw(qdecimals(alpha * px**2, (D(1) / alpha * px).sqrt()))
    # assert(px / py**2 >= alpha)
    # assert(py / px**2 >= alpha)
    assume(px * py >= alpha)
    return px, py


@st.composite
def gen_synthetic_balances_via_prices(draw, bparams: BasicPoolParameters, root3Alpha_min: D, root3Alpha_max: D):
    """Generates an invariant and a price, and from that balances using math from the CPMMv3 paper.

    Due to rounding errors, the relationship does not hold exactly, i.e., the generated balances also have an error attached.
    
    NOTE: There seems to be no advantage using this over gen_synthetic_balances(); prices can be computed when in doubt. Perhaps if one needs specifically chosen prices, but otherwise you're prob better off with the other function.""" 
    root3Alpha = draw(qdecimals(root3Alpha_min, root3Alpha_max))
    alpha = root3Alpha**3

    prices = draw(gen_feasible_prices(alpha))

    # OPEN if this is the right ballpark. Dep/ on alpha, too. But I hope it's fine.
    invariant = draw(qdecimals(1, 100_000_000_000))

    # See Prop. 9.
    px, py = prices
    gamma = (px * py)**(D(1)/3)

    factors = [
        gamma / px - root3Alpha,
        gamma / py - root3Alpha,
        gamma - root3Alpha,
    ]

    for i in range(3):
        # These will only hold approximately b/c of rounding errors.
        assert factors[i] >= D(0).approxed()
        factors[i] = max(factors[i], D(0))

    balances = [f * invariant for f in factors]

    return balances, invariant, prices, root3Alpha


@st.composite
def gen_synthetic_balances(draw, bpool_params: BasicPoolParameters, root3Alpha_min: D, root3Alpha_max: D,
                           min_balance: D = D(1)):
    """This is more accurate than gen_synthetic_balances_via_prices()."""
    root3Alpha = draw(qdecimals(root3Alpha_min, root3Alpha_max))

    # OPEN if the bounds are right.
    invariant = draw(qdecimals(1, 100_000_000_000))

    virtOffset = invariant * root3Alpha

    # We choose x, y, z, in order. The bounds are such that all balances are non-negative and have the given invariant.
    # To see this, go from z to x backwards or see Steffen's notebook p. 148.
    xmax = invariant / (root3Alpha**2) - virtOffset
    assume(min_balance <= xmax)
    x = draw(qdecimals(1, xmax))
    ymax = min(
        invariant**2 / (root3Alpha * (x + virtOffset)) - virtOffset,
        x / bpool_params.min_balance_ratio
    )
    ymin = max(x * bpool_params.min_balance_ratio, min_balance)
    assume(ymin <= ymax)
    y = draw(qdecimals(ymin, ymax))
    z = invariant**3 / ((x + virtOffset) * (y + virtOffset)) - virtOffset

    assume(z >= min_balance)
    assume(y / bpool_params.min_balance_ratio >= z >= y * bpool_params.min_balance_ratio)
    assume(x / bpool_params.min_balance_ratio >= z >= x * bpool_params.min_balance_ratio)

    balances = (x, y, z)

    return balances, invariant, root3Alpha
