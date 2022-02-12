from math import pi, sin, cos, tan

from hypothesis import strategies as st, assume

from brownie import reverts

from tests.cemm import cemm as mimpl
from tests.support.quantized_decimal import QuantizedDecimal as D
from tests.support.types import CEMMMathParams, CEMMMathDerivedParams, Vector2
from tests.support.utils import qdecimals, scale, to_decimal, unscale

billion_balance_strategy = st.integers(min_value=0, max_value=1_000_000_000)


def params2MathParams(params: CEMMMathParams) -> mimpl.Params:
    """The python math implementation is a bit older and uses its own data structures. This function converts."""
    return mimpl.Params(params.alpha, params.beta, params.c, -params.s, params.l)


def mathParams2DerivedParams(mparams: mimpl.Params) -> CEMMMathDerivedParams:
    return CEMMMathDerivedParams(
        tauAlpha=Vector2(*mparams.tau_alpha), tauBeta=Vector2(*mparams.tau_beta)
    )


@st.composite
def gen_params(draw):
    phi_degrees = draw(st.floats(10, 80))
    phi = phi_degrees / 360 * 2 * pi

    # Price bounds. Choose s.t. the 'peg' lies approximately within the bounds (within 30%).
    # It'd be nonsensical if this was not the case: Why are we using an ellipse then?!
    peg = tan(phi)  # = price where the flattest point of the ellipse lies.
    peg = D(peg)
    alpha_high = peg * D("1.3")
    beta_low = peg * D("0.7")
    alpha = draw(qdecimals("0.05", alpha_high.raw))
    beta = draw(qdecimals(beta_low, "20.0"))

    s = sin(phi)
    c = cos(phi)
    l = draw(qdecimals("1", "10"))
    return CEMMMathParams(alpha, beta, D(c), D(s), l)


def gen_balances():
    return st.tuples(billion_balance_strategy, billion_balance_strategy)


def gen_balances_vector():
    return gen_balances().map(lambda args: Vector2(*args))


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


#####################################################################
### helper functions for testing math library


def mtest_mulAinv(params: CEMMMathParams, t: Vector2, gyro_cemm_math_testing):
    mparams = params2MathParams(params)
    res_sol = gyro_cemm_math_testing.mulAinv(scale(params), scale(t))
    res_math = mparams.Ainv_times(t.x, t.y)
    # For some reason we need to convert here, o/w the test fails even when they are equal.
    # Note: This is scaled, so tolerance 10 means the previous to last decimal must match, the last one can differ.
    # There's no relative tolerance.
    assert int(res_sol[0]) == scale(res_math[0])
    assert int(res_sol[1]) == scale(res_math[1])


def mtest_mulA(params: CEMMMathParams, t: Vector2, gyro_cemm_math_testing):
    mparams = params2MathParams(params)
    res_sol = gyro_cemm_math_testing.mulA(scale(params), scale(t))
    res_math = mparams.A_times(t.x, t.y)
    # For some reason we need to convert here, o/w the test fails even when they are equal.
    assert int(res_sol[0]) == scale(res_math[0])
    assert int(res_sol[1]) == scale(res_math[1])


def mtest_zeta(params_px, gyro_cemm_math_testing):
    (
        params,
        px,
    ) = params_px  # Annoying manual unpacking b/c hypothesis is oddly limited at dependent arguments.
    mparams = params2MathParams(params)
    res_sol = gyro_cemm_math_testing.zeta(scale(params), scale(px))
    res_math = mparams.zeta(px)
    assert int(res_sol) == scale(res_math)


def mtest_tau(params_px, gyro_cemm_math_testing):
    # tau is as precise as eta.
    params, px = params_px
    mparams = params2MathParams(params)
    res_sol = gyro_cemm_math_testing.tau(scale(params), scale(px))
    res_math = mparams.tau(px)
    assert int(res_sol[0]) == scale(res_math[0]).approxed(abs=D("1e5"), rel=D("1e-16"))
    assert int(res_sol[1]) == scale(res_math[1]).approxed(abs=D("1e5"), rel=D("1e-16"))


def mk_CEMMMathDerivedParams_from_brownie(args):
    apair, bpair = args
    return CEMMMathDerivedParams(Vector2(*apair), Vector2(*bpair))


def mtest_mkDerivedParams(params, gyro_cemm_math_testing):
    # Accuracy of the derived params is that of tau.
    mparams = params2MathParams(params)
    derived_sol = mk_CEMMMathDerivedParams_from_brownie(
        gyro_cemm_math_testing.mkDerivedParams(scale(params))
    )
    assert int(derived_sol.tauAlpha.x) == scale(mparams.tau_alpha[0]).approxed(
        abs=D("1e5"), rel=D("1e-16")
    )
    assert int(derived_sol.tauAlpha.y) == scale(mparams.tau_alpha[1]).approxed(
        abs=D("1e5"), rel=D("1e-16")
    )
    assert int(derived_sol.tauBeta.x) == scale(mparams.tau_beta[0]).approxed(
        abs=D("1e5"), rel=D("1e-16")
    )
    assert int(derived_sol.tauBeta.y) == scale(mparams.tau_beta[1]).approxed(
        abs=D("1e5"), rel=D("1e-16")
    )


def gen_synthetic_invariant():
    """Generate invariant for cases where it *doesn't* have to match any balances."""
    return qdecimals(1, 100_000_000_000)


def gtest_virtualOffsets(
    params, invariant, derived_scaled, gyro_cemm_math_testing, abs, rel
):
    mparams = params2MathParams(params)
    ab_sol = gyro_cemm_math_testing.virtualOffsets(
        scale(params), derived_scaled, scale(invariant)
    )

    # The python implementation has this function part of the pool structure even though it only needs the invariant.
    cemm = mimpl.CEMM.from_px_r(D(1), invariant, mparams)

    assert int(ab_sol[0]) == scale(cemm.a).approxed(abs=abs, rel=rel)
    assert int(ab_sol[1]) == scale(cemm.b).approxed(abs=abs, rel=rel)


def mtest_virtualOffsets_noderived(params, invariant, gyro_cemm_math_testing):
    """Test Calculation of just the virtual offsets, not including the derived params calculation. This is exact."""
    derived_scaled = scale(mathParams2DerivedParams(params2MathParams(params)))
    return gtest_virtualOffsets(
        params, invariant, derived_scaled, gyro_cemm_math_testing, 0, 0
    )


def mtest_virtualOffsets_with_derived(params, invariant, gyro_cemm_math_testing):
    """Test Calculation of just the virtual offsets, not including the derived params calculation. This is exact."""
    derived_scaled = mk_CEMMMathDerivedParams_from_brownie(
        gyro_cemm_math_testing.mkDerivedParams(scale(params))
    )
    return gtest_virtualOffsets(
        params, invariant, derived_scaled, gyro_cemm_math_testing, D("1e5"), D("1e-16")
    )


def mtest_maxBalances(params, invariant, gyro_cemm_math_testing):
    mparams = params2MathParams(params)
    derived_sol = mk_CEMMMathDerivedParams_from_brownie(
        gyro_cemm_math_testing.mkDerivedParams(scale(params))
    )
    xy_sol = gyro_cemm_math_testing.maxBalances(
        scale(params), derived_sol, scale(invariant)
    )

    # The python implementation has this function part of the pool structure even though it only needs the invariant.
    cemm = mimpl.CEMM.from_px_r(D(1), invariant, mparams)

    assert int(xy_sol[0]) == scale(cemm.xmax).approxed()
    assert int(xy_sol[1]) == scale(cemm.ymax).approxed()


#####################################################################
### for testing the main math library functions


def mtest_calculateInvariant(params, balances, gyro_cemm_math_testing):
    mparams = params2MathParams(params)
    derived_sol = mk_CEMMMathDerivedParams_from_brownie(
        gyro_cemm_math_testing.mkDerivedParams(scale(params))
    )
    uinvariant_sol = gyro_cemm_math_testing.calculateInvariant(
        scale(balances), scale(params), derived_sol
    )

    cemm = mimpl.CEMM.from_x_y(balances[0], balances[1], mparams)

    return (
        cemm.r,
        D(int(uinvariant_sol)),
    )


def mtest_calculatePrice(params, balances, gyro_cemm_math_testing):
    assume(balances != (0, 0))

    mparams = params2MathParams(params)
    derived_sol = mk_CEMMMathDerivedParams_from_brownie(
        gyro_cemm_math_testing.mkDerivedParams(scale(params))
    )

    cemm = mimpl.CEMM.from_x_y(balances[0], balances[1], mparams)

    price_sol = gyro_cemm_math_testing.calculatePrice(
        scale(balances), scale(params), derived_sol, scale(cemm.r)
    )

    return cemm.px, to_decimal(price_sol)


def mtest_calcYGivenX(params, x, invariant, gyro_cemm_math_testing):
    assume(x == 0 if invariant == 0 else True)

    mparams = params2MathParams(params)
    derived_sol = mk_CEMMMathDerivedParams_from_brownie(
        gyro_cemm_math_testing.mkDerivedParams(scale(params))
    )

    midprice = (params.alpha + params.beta) / 2
    cemm = mimpl.CEMM.from_px_r(midprice, invariant, mparams)  # Price doesn't matter.

    y = cemm._compute_y_for_x(x)
    assume(y is not None)  # O/w out of bounds for this invariant

    y_sol = gyro_cemm_math_testing.calcYGivenX(
        scale(x), scale(params), derived_sol, scale(cemm.r)
    )
    return y, to_decimal(y_sol)


def test_calcXGivenY(params, y, invariant, gyro_cemm_math_testing):
    assume(y == 0 if invariant == 0 else True)

    mparams = params2MathParams(params)
    derived_sol = mk_CEMMMathDerivedParams_from_brownie(
        gyro_cemm_math_testing.mkDerivedParams(scale(params))
    )

    midprice = (params.alpha + params.beta) / 2
    cemm = mimpl.CEMM.from_px_r(midprice, invariant, mparams)  # Price doesn't matter.

    x = cemm._compute_x_for_y(y)
    assume(x is not None)  # O/w out of bounds for this invariant

    x_sol = gyro_cemm_math_testing.calcXGivenY(
        scale(y), scale(params), derived_sol, scale(cemm.r)
    )
    return x, to_decimal(x_sol)


def test_calcOutGivenIn(
    params, balances, amountIn, tokenInIsToken0, gyro_cemm_math_testing
):
    ixIn = 0 if tokenInIsToken0 else 1
    ixOut = 1 - ixIn

    assume(amountIn <= to_decimal("0.3") * balances[ixIn])

    mparams = params2MathParams(params)
    derived_sol = mk_CEMMMathDerivedParams_from_brownie(
        gyro_cemm_math_testing.mkDerivedParams(scale(params))
    )

    cemm = mimpl.CEMM.from_x_y(balances[0], balances[1], mparams)

    r = cemm.r

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
                derived_sol,
                scale(r),
            )
        return

    amountOut = -mamountOut
    assert r == cemm.r  # just to be sure

    amountOut_sol = gyro_cemm_math_testing.calcOutGivenIn(
        scale(balances),
        scale(amountIn),
        tokenInIsToken0,
        scale(params),
        derived_sol,
        scale(r),
    )

    return amountOut, to_decimal(amountOut_sol)


def mtest_calcInGivenOut(
    params, balances, amountOut, tokenInIsToken0, gyro_cemm_math_testing
):
    ixIn = 0 if tokenInIsToken0 else 1
    ixOut = 1 - ixIn

    assume(amountOut <= to_decimal("0.3") * balances[ixOut])

    mparams = params2MathParams(params)
    derived_sol = mk_CEMMMathDerivedParams_from_brownie(
        gyro_cemm_math_testing.mkDerivedParams(scale(params))
    )

    cemm = mimpl.CEMM.from_x_y(balances[0], balances[1], mparams)

    r = cemm.r

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
                derived_sol,
                scale(r),
            )
        return

    assert r == cemm.r  # just to be sure

    amountIn_sol = gyro_cemm_math_testing.calcInGivenOut(
        scale(balances),
        scale(amountOut),
        tokenInIsToken0,
        scale(params),
        derived_sol,
        scale(r),
    )
    return amountIn, to_decimal(amountIn_sol)


def mtest_calculateSqrtOnePlusZetaSquared(params, balances, gyro_cemm_math_testing):
    # This is a comparison test that also tests the basic math behind this: The solidity code doesn't actually
    # calculate the square root!
    assume(balances != (0, 0))

    mparams = params2MathParams(params)
    derived_sol = mk_CEMMMathDerivedParams_from_brownie(
        gyro_cemm_math_testing.mkDerivedParams(scale(params))
    )
    cemm = mimpl.CEMM.from_x_y(balances[0], balances[1], mparams)

    val_explicit = (D(1) + mparams.zeta(cemm.px) ** 2).sqrt()
    val_implicit = cemm._sqrtOnePlusZetaSquared
    val_sol = gyro_cemm_math_testing.calculateSqrtOnePlusZetaSquared(
        scale(balances), scale(params), derived_sol, scale(cemm.r)
    )

    assert (
        val_explicit == val_implicit.approxed()
    )  # Tests math / the python implementation
    return val_implicit, to_decimal(val_sol)


def mtest_liquidityInvariantUpdate(params_cemm_dinvariant, gyro_cemm_math_testing):
    params, cemm, dinvariant = params_cemm_dinvariant
    assume(cemm.x != 0 or cemm.y != 0)

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

    return rnew, to_decimal(rnew_sol)


def mtest_liquidityInvariantUpdateEquivalence(
    params_cemm_dinvariant, gyro_cemm_math_testing
):
    """Tests a mathematical fact. Doesn't test solidity."""
    params, cemm, dinvariant = params_cemm_dinvariant
    assume(cemm.x != 0 or cemm.y != 0)

    r = cemm.r
    dx, dy = cemm.update_liquidity(dinvariant, mock=True)

    # To try it out even
    assert dx == (dinvariant / r * cemm.x).approxed(abs=1e-5)
    assert dy == (dinvariant / r * cemm.y).approxed(abs=1e-5)
