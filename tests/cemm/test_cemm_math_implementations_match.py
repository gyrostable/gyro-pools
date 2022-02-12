import hypothesis.strategies as st
from brownie.test import given
from brownie import reverts
from hypothesis import assume, settings, example
from tests.cemm import cemm as mimpl
from tests.cemm.util import params2MathParams, mathParams2DerivedParams, gen_params, gen_balances, gen_balances_vector, \
    gen_params_cemm_dinvariant
from tests.support.utils import scale, to_decimal, qdecimals, unscale
from tests.support.types import *
from tests.support.quantized_decimal import QuantizedDecimal as D
from tests.support.quantized_decimal import QuantizedDecimal as Decimal

# this is a multiplicative separation
# This is consistent with tightest price range of beta - alpha >= MIN_PRICE_SEPARATION
MIN_PRICE_SEPARATION = to_decimal("0.0001")


def faulty_params(balances, params: CEMMMathParams):
    balances = [to_decimal(b) for b in balances]
    if balances[0] == 0 and balances[1] == 0:
        return True
    return 0 >= params.beta - params.alpha >= MIN_PRICE_SEPARATION


# Sry monkey patching...
# Default absolute tolerance is 1e-12 but we're scaled by 1e18, so we actually want 1e6.
# Note that the relative threshold should *not* be scaled, but it still needs to be mentioned, o/w it's assumed to be equal to 0.
# For some calculations, we choose laxer bounds of abs=1e-3 (scaled: 1e15) and rel=1e-6.
D.approxed_scaled = lambda self: self.approxed(abs=D("1E6"), rel=D("1E-6"))
D.our_approxed_scaled = lambda self: self.approxed(abs=D("1E15"), rel=D("1E-6"))


@given(params=gen_params(), t=gen_balances_vector())
def test_mulAinv(params: CEMMMathParams, t: Vector2, gyro_cemm_math_testing):
    mparams = params2MathParams(params)
    res_sol = gyro_cemm_math_testing.mulAinv(scale(params), scale(t))
    res_math = mparams.Ainv_times(t.x, t.y)
    # For some reason we need to convert here, o/w the test fails even when they are equal.
    # Note: This is scaled, so tolerance 10 means the previous to last decimal must match, the last one can differ.
    # There's no relative tolerance.
    assert int(res_sol[0]) == scale(res_math[0])
    assert int(res_sol[1]) == scale(res_math[1])

@given(params=gen_params(), t=gen_balances_vector())
def test_mulA(params: CEMMMathParams, t: Vector2, gyro_cemm_math_testing):
    mparams = params2MathParams(params)
    res_sol = gyro_cemm_math_testing.mulA(scale(params), scale(t))
    res_math = mparams.A_times(t.x, t.y)
    # For some reason we need to convert here, o/w the test fails even when they are equal.
    assert int(res_sol[0]) == scale(res_math[0])
    assert int(res_sol[1]) == scale(res_math[1])


@st.composite
def gen_params_px(draw):
    params = draw(gen_params())
    px = draw(qdecimals(params.alpha.raw, params.beta.raw))
    return params, px

@given(params_px=gen_params_px())
def test_zeta(params_px, gyro_cemm_math_testing):
    (
        params,
        px,
    ) = params_px  # Annoying manual unpacking b/c hypothesis is oddly limited at dependent arguments.
    mparams = params2MathParams(params)
    res_sol = gyro_cemm_math_testing.zeta(scale(params), scale(px))
    res_math = mparams.zeta(px)
    assert int(res_sol) == scale(res_math)

@given(pxc=qdecimals('-1E16', '1E16'))
def test_eta(pxc, gyro_cemm_math_testing):
    # eta is very precise in the grand scheme of things, but of course we can't be more precise than sqrt() across the range of values we care about.
    # Note that eta does *not* depend on params.
    res_sol = gyro_cemm_math_testing.eta(scale(pxc))
    res_math = mimpl.eta(pxc)
    assert int(res_sol[0]) == scale(res_math[0]).approxed(abs=D('1e5'), rel=D('1e-16'))
    assert int(res_sol[1]) == scale(res_math[1]).approxed(abs=D('1e5'), rel=D('1e-16'))

@given(params_px=gen_params_px())
def test_tau(params_px, gyro_cemm_math_testing):
    # tau is as precise as eta.
    params, px = params_px
    mparams = params2MathParams(params)
    res_sol = gyro_cemm_math_testing.tau(scale(params), scale(px))
    res_math = mparams.tau(px)
    assert int(res_sol[0]) == scale(res_math[0]).approxed(abs=D('1e5'), rel=D('1e-16'))
    assert int(res_sol[1]) == scale(res_math[1]).approxed(abs=D('1e5'), rel=D('1e-16'))


def mk_CEMMMathDerivedParams_from_brownie(args):
    apair, bpair = args
    return CEMMMathDerivedParams(Vector2(*apair), Vector2(*bpair))

@given(params=gen_params())
def test_mkDerivedParams(params, gyro_cemm_math_testing):
    # Accuracy of the derived params is that of tau.
    mparams = params2MathParams(params)
    derived_sol = mk_CEMMMathDerivedParams_from_brownie(
        gyro_cemm_math_testing.mkDerivedParams(scale(params))
    )
    assert int(derived_sol.tauAlpha.x) == scale(mparams.tau_alpha[0]).approxed(abs=D('1e5'), rel=D('1e-16'))
    assert int(derived_sol.tauAlpha.y) == scale(mparams.tau_alpha[1]).approxed(abs=D('1e5'), rel=D('1e-16'))
    assert int(derived_sol.tauBeta.x) == scale(mparams.tau_beta[0]).approxed(abs=D('1e5'), rel=D('1e-16'))
    assert int(derived_sol.tauBeta.y) == scale(mparams.tau_beta[1]).approxed(abs=D('1e5'), rel=D('1e-16'))


### Virtual Offsets and Max Balances ###


def gen_synthetic_invariant():
    """Generate invariant for cases where it *doesn't* have to match any balances."""
    return qdecimals(1, 100_000_000_000)

@given(params=gen_params(), invariant=gen_synthetic_invariant())
@example(
    params=CEMMMathParams(alpha=Decimal('0.302137159231720000'), beta=Decimal('1.005000000000000000'),
                          c=Decimal('0.836049436859842232'), s=Decimal('0.548654116111727208'),
                          l=Decimal('2.960000000000000000')),
    invariant=Decimal('32034653686.598895308700000000'),
)
def test_virtualOffsets_noderived(params, invariant, gyro_cemm_math_testing):
    """Test Calculation of just the virtual offsets, not including the derived params calculation. This is exact."""
    derived_scaled = scale(mathParams2DerivedParams(params2MathParams(params)))
    return gtest_virtualOffsets(params, invariant, derived_scaled, gyro_cemm_math_testing, 0, 0)

@settings(max_examples=1_000)
@given(params=gen_params(), invariant=gen_synthetic_invariant())
@example(
    params=CEMMMathParams(alpha=Decimal('0.302137159231720000'), beta=Decimal('1.005000000000000000'),
                          c=Decimal('0.836049436859842232'), s=Decimal('0.548654116111727208'),
                          l=Decimal('2.960000000000000000')),
    invariant=Decimal('32034653686.598895308700000000'),
)
def test_virtualOffsets_with_derived(params, invariant, gyro_cemm_math_testing):
    """Test Calculation of just the virtual offsets, not including the derived params calculation. This is exact."""
    derived_scaled = mk_CEMMMathDerivedParams_from_brownie(
        gyro_cemm_math_testing.mkDerivedParams(scale(params))
    )
    return gtest_virtualOffsets(params, invariant, derived_scaled, gyro_cemm_math_testing,
                                D('1e5'), D('1e-16'))

def gtest_virtualOffsets(params, invariant, derived_scaled, gyro_cemm_math_testing, abs, rel):
    mparams = params2MathParams(params)
    ab_sol = gyro_cemm_math_testing.virtualOffsets(
        scale(params), derived_scaled, scale(invariant)
    )

    # The python implementation has this function part of the pool structure even though it only needs the invariant.
    cemm = mimpl.CEMM.from_px_r(D(1), invariant, mparams)

    assert int(ab_sol[0]) == scale(cemm.a).approxed(abs=abs, rel=rel)
    assert int(ab_sol[1]) == scale(cemm.b).approxed(abs=abs, rel=rel)

@settings(max_examples=1_000)
@given(params=gen_params(), invariant=gen_synthetic_invariant())
def test_maxBalances(params, invariant, gyro_cemm_math_testing):
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


# We don't test chi b/c there is no separate function for it in the math implementation. This is tested in
# calculateInvariant()

# NOTE: This test FAILS when the parameters can be arbitrary. However, these functions *are* tested the way they're
# actually used below.

# @given(
#     qparams=st.builds(CEMMMathQParams, qdecimals(), qdecimals(), qdecimals())
# )
# def test_solveQuadratic(qparams: CEMMMathQParams, gyro_cemm_math_testing):
#     a, b, c = qparams
#     assume(a != 0)
#
#     d = b*b - D(4)*a*c
#     if d < 0:
#         with reverts("SafeCast: value must be positive"):
#             gyro_cemm_math_testing.solveQuadraticPlus(scale(qparams))
#         with reverts("SafeCast: value must be positive"):
#             gyro_cemm_math_testing.solveQuadraticMinus(scale(qparams))
#         return
#
#     # We don't compare to the real solutions (see commented-out below). Accuracy is hard to check here. Instead, we
#     # check against 0.
#     xplus_sol = gyro_cemm_math_testing.solveQuadraticPlus(scale(qparams))
#     xminus_sol = gyro_cemm_math_testing.solveQuadraticMinus(scale(qparams))
#
#     xplus = (-b + d.sqrt()) / (D(2)*a)
#     xminus = (-b - d.sqrt()) / (D(2)*a)
#
#     # abs tolerances are what we use for the CPMMv3 to test calculating the invariant. It's kinda
#     # hard to test this in isolation without knowledge how big the coefficients are gonna be.
#     assert int(xplus_sol) == scale(xplus).approxed(abs=1e15)
#     assert int(xminus_sol) == scale(xminus).approxed(abs=1e15)

@settings(max_examples=1_000)
@given(params=gen_params(), balances=gen_balances())
def test_calculateInvariant(params, balances, gyro_cemm_math_testing):
    mparams = params2MathParams(params)
    derived_sol = mk_CEMMMathDerivedParams_from_brownie(
        gyro_cemm_math_testing.mkDerivedParams(scale(params))
    )
    uinvariant_sol = gyro_cemm_math_testing.calculateInvariant(
        scale(balances), scale(params), derived_sol
    )

    cemm = mimpl.CEMM.from_x_y(balances[0], balances[1], mparams)

    # We now require that the invariant is underestimated and allow ourselves a bit of slack in the other direction.
    assert D(int(uinvariant_sol)).approxed_scaled() <= scale(cemm.r).approxed_scaled()
    assert int(uinvariant_sol) == scale(cemm.r).approxed(
        abs=1e15, rel=to_decimal("1E-6")
    )

@settings(max_examples=1_000)
@given(params=gen_params(), balances=gen_balances())
def test_calculatePrice(params, balances, gyro_cemm_math_testing):
    assume(balances != (0, 0))

    mparams = params2MathParams(params)
    derived_sol = mk_CEMMMathDerivedParams_from_brownie(
        gyro_cemm_math_testing.mkDerivedParams(scale(params))
    )

    cemm = mimpl.CEMM.from_x_y(balances[0], balances[1], mparams)

    price_sol = gyro_cemm_math_testing.calculatePrice(
        scale(balances), scale(params), derived_sol, scale(cemm.r)
    )

    assert to_decimal(price_sol) == scale(cemm.px).approxed_scaled()


# checkAssetBounds() not tested.

@settings(max_examples=1_000)
@given(
    params=gen_params(),
    x=qdecimals(0, 100_000_000_000),
    invariant=gen_synthetic_invariant(),
)
def test_calcYGivenX(params, x, invariant, gyro_cemm_math_testing):
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
    assert to_decimal(y_sol) == scale(y).approxed_scaled()

@settings(max_examples=1_000)
@given(
    params=gen_params(),
    y=qdecimals(0, 100_000_000_000),
    invariant=gen_synthetic_invariant(),
)
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
    assert to_decimal(x_sol) == scale(x).approxed_scaled()

@settings(max_examples=1_000)
@given(
    params=gen_params(),
    balances=gen_balances(),
    amountIn=qdecimals(min_value=1, max_value=1_000_000_000, places=4),
    tokenInIsToken0=st.booleans(),
)
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

    assert to_decimal(amountOut_sol) == scale(
        amountOut
    ).our_approxed_scaled() or to_decimal(amountOut_sol) == scale(amountOut).approxed(
        abs=D("1E6") * balances[ixOut]
    )
    # ^ The second case catches some pathological test cases where an error on the order of 1e-3 occurs in
    # an extremely unbalanced pool with reserves on the order of (100M, 1).
    # Differences smaller than 1e-12 * balances are ignored.

@settings(max_examples=1_000)
@given(
    params=gen_params(),
    balances=gen_balances(),
    amountOut=qdecimals(min_value=1, max_value=1_000_000_000, places=4),
    tokenInIsToken0=st.booleans(),
)
def test_calcInGivenOut(
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

    assert to_decimal(amountIn_sol) == scale(
        amountIn
    ).our_approxed_scaled() or to_decimal(amountIn_sol) == scale(amountIn).approxed(
        abs=D("1E6") * balances[ixOut]
    )

@settings(max_examples=1_000)
@given(
    params=gen_params(),
    balances=gen_balances(),
)
def test_calculateSqrtOnePlusZetaSquared(params, balances, gyro_cemm_math_testing):
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
    assert to_decimal(val_sol) == scale(val_implicit).approxed_scaled()


@settings(max_examples=1_000)
@given(params_cemm_dinvariant=gen_params_cemm_dinvariant())
def test_liquidityInvariantUpdate(params_cemm_dinvariant, gyro_cemm_math_testing):
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

    assert unscale(to_decimal(rnew_sol)) == rnew.approxed()

@settings(max_examples=1_000)
@given(params_cemm_dinvariant=gen_params_cemm_dinvariant())
def test_liquidityInvariantUpdateEquivalence(
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


# BPT token and protocol fee calculations are not tested b/c they're exactly the same as for the other pools.
