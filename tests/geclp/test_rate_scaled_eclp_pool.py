import pytest
from brownie import ZERO_ADDRESS, MockRateProvider

from tests.g2clp import constants
from .test_eclp_pool import join_pool
from .util import params2MathParams
from ..support.types import ECLPMathParams, SwapRequest, SwapKind
from ..support.utils import (
    unscale,
    to_decimal as D,
    approxed,
    scale,
    get_transfer_event,
    get_invariant_div_supply,
)
from . import eclp_prec_implementation as math_implementation
from . import eclp as math_implementation_old

# Tests are copied and adapted from test_eclp_pool.py


def test_pool_reg(mock_vault, rate_scaled_eclp_pool, gyro_erc20_funded):
    eclp_pool = rate_scaled_eclp_pool
    poolId = eclp_pool.getPoolId()
    print("Pool ID", poolId)

    # Check pool and token registration
    (token_addresses, token_balances) = mock_vault.getPoolTokens(poolId)

    for token in range(constants.NUM_TOKENS):
        assert token_addresses[token] == gyro_erc20_funded[token].address
        assert token_balances[token] == 0


def rate_scale_balances(rate_scaled_eclp_pool, balances):
    ret = list(balances)

    if rate_scaled_eclp_pool.rateProvider0() != ZERO_ADDRESS:
        rateProvider0 = MockRateProvider.at(rate_scaled_eclp_pool.rateProvider0())
        ret[0] *= unscale(rateProvider0.getRate())
    if rate_scaled_eclp_pool.rateProvider1() != ZERO_ADDRESS:
        rateProvider1 = MockRateProvider.at(rate_scaled_eclp_pool.rateProvider1())
        ret[1] *= unscale(rateProvider1.getRate())
    return ret


def get_eclp_params_args(eclp_pool):
    """Fetch appropriately-scaled ECLP parameters from pool"""
    params, derived = eclp_pool.getECLPParams()
    return math_implementation.unscale_params(
        math_implementation.Params(*params)
    ), math_implementation.unscale_derived_values(
        math_implementation.DerivedParams(*derived)
    )


def test_pool_on_initialize(
    users, rate_scaled_eclp_pool, mock_rate_provider, mock_vault
):
    eclp_pool = rate_scaled_eclp_pool
    mock_rate_provider.mockRate(scale("1.5"))

    # Test factors (DEBUG)
    # factors = unscale(rate_scaled_eclp_pool.getScalingFactors())
    # assert factors[0] == D("1.5")
    # assert factors[1] == D(1)

    balances = (0, 0)
    amountIn = 100 * 10**18

    tx = join_pool(mock_vault, eclp_pool.address, users[0], balances, amountIn)

    poolId = eclp_pool.getPoolId()

    # Check Pool balance change
    assert tx.events["PoolBalanceChanged"]["poolId"] == poolId
    assert tx.events["PoolBalanceChanged"]["liquidityProvider"] == users[0]

    assert tx.events["PoolBalanceChanged"]["deltas"] == (amountIn, amountIn)
    assert tx.events["PoolBalanceChanged"]["protocolFees"] == (0, 0)

    # Check BPT Token minting
    assert tx.events["Transfer"][1]["from"] == ZERO_ADDRESS
    assert tx.events["Transfer"][1]["to"] == users[0]
    initial_bpt_tokens = tx.events["Transfer"][1]["value"]
    assert initial_bpt_tokens > 0

    # Note: This is only a very approximate check. The resulting (rate-scaled) pool price is not 1! But since the price
    # range is pretty narrow, it's going to be close to 1.
    assert unscale(initial_bpt_tokens) == unscale(amountIn * D("2.5")).approxed(abs=3)

    # Check that the amountIn is now stored in the pool balance
    (_, initial_balances) = mock_vault.getPoolTokens(poolId)
    assert initial_balances[0] == amountIn
    assert initial_balances[1] == amountIn

    # Test value of the invariant
    invariant = unscale(eclp_pool.getInvariant())

    eclp_params_args = get_eclp_params_args(eclp_pool)
    rate_scaled_balances = rate_scale_balances(
        rate_scaled_eclp_pool, unscale(initial_balances)
    )
    invariant_expected = math_implementation.calculateInvariant(
        rate_scaled_balances, *eclp_params_args
    )

    assert invariant == invariant_expected.approxed()


def test_pool_on_exit(
    users, rate_scaled_eclp_pool, mock_vault, mock_rate_provider, gyro_eclp_math_testing
):
    eclp_pool = rate_scaled_eclp_pool
    ratex = D("1.5")
    mock_rate_provider.mockRate(scale(ratex))

    # We perform a join that will have equal values *after scaling*
    amount_in = 100 * 10**18
    amounts_in = (int(amount_in / ratex), amount_in)

    tx = join_pool(mock_vault, eclp_pool.address, users[0], (0, 0), amounts_in)

    poolId = eclp_pool.getPoolId()
    (_, initial_balances) = mock_vault.getPoolTokens(poolId)
    tx = join_pool(
        mock_vault,
        eclp_pool.address,
        users[1],
        initial_balances,
        amounts_in,
        amount_out=eclp_pool.totalSupply(),
    )

    amount_out = 5 * 10**18
    amounts_out = (int(amount_out / ratex), amount_out)

    # We use actual supply, not totalSupply here because a tiny amount of protocol fees may be paid due to rounding errors.
    actual_supply_before_exit = eclp_pool.getActualSupply()
    (_, balances_after_join) = mock_vault.getPoolTokens(poolId)

    invariant_after_join = eclp_pool.getLastInvariant()

    bptTokensToBurn = eclp_pool.balanceOf(users[0]) * amount_out // amount_in
    tx = mock_vault.callExitPoolGyro(
        eclp_pool.address,
        0,
        users[0],
        users[0],
        balances_after_join,
        0,
        0,
        bptTokensToBurn,
    )

    assert unscale(tx.events["PoolBalanceChanged"]["deltas"]) == approxed(
        unscale(amounts_out)
    )

    (_, balancesAfterExit) = mock_vault.getPoolTokens(poolId)
    assert int(balancesAfterExit[0]) == pytest.approx(
        balances_after_join[0] - amounts_out[0]
    )
    assert int(balancesAfterExit[1]) == pytest.approx(
        balances_after_join[1] - amounts_out[1]
    )

    ## Check BTP Token minting
    ev = get_transfer_event(tx, from_addr=users[0])
    assert ev["to"] == ZERO_ADDRESS
    bptTokensburnt = ev["value"]
    assert bptTokensburnt > 0
    # Check that approx. amount of tokens burnt is proportional to the amount of tokens substracted from the pool
    assert unscale(bptTokensburnt) == approxed(
        unscale(actual_supply_before_exit * amounts_out[0] // balances_after_join[0])
    )
    assert bptTokensburnt == bptTokensToBurn

    sparams, sdparams = eclp_pool.getECLPParams()

    ## Check new pool's invariant
    invariant_after_exit = eclp_pool.getLastInvariant()
    assert invariant_after_join > invariant_after_exit

    # This is the value used in _onExitPool(): The invariant is recalculated each time.
    # B/c recalculation isn't perfectly precise, we only match the stored value approximately.
    balances_after_join_ratescaled = [
        int(balances_after_join[0] * ratex),
        balances_after_join[1],
    ]
    sInvariant_after_join = gyro_eclp_math_testing.calculateInvariant(
        balances_after_join_ratescaled, sparams, sdparams
    )
    assert unscale(sInvariant_after_join) == unscale(invariant_after_join).approxed()

    sInvariant_after_exit = gyro_eclp_math_testing.liquidityInvariantUpdate(
        sInvariant_after_join, bptTokensToBurn, actual_supply_before_exit, False
    )

    assert invariant_after_exit == sInvariant_after_exit


def test_pool_swap(
    users, rate_scaled_eclp_pool, mock_vault, mock_rate_provider, gyro_erc20_funded
):
    eclp_pool = rate_scaled_eclp_pool
    ratex = D("1.5")
    mock_rate_provider.mockRate(scale(ratex))

    amount_in = 100 * 10**18
    amounts_in = (int(amount_in / ratex), amount_in)

    tx = join_pool(mock_vault, eclp_pool.address, users[0], (0, 0), amounts_in)

    poolId = eclp_pool.getPoolId()
    (_, initial_balances) = mock_vault.getPoolTokens(poolId)
    tx = join_pool(
        mock_vault,
        eclp_pool.address,
        users[1],
        initial_balances,
        amounts_in,
        amount_out=eclp_pool.totalSupply(),
    )

    (_, balances) = mock_vault.getPoolTokens(poolId)
    rate_scaled_balances = (int(balances[0] * ratex), balances[1])

    amount_to_swap = 10 * 10**18

    fees = amount_to_swap * unscale(eclp_pool.getSwapFeePercentage())
    amountToSwapMinusFees = amount_to_swap - fees
    amountToSwapMinusFees_ratescaled = amountToSwapMinusFees * ratex

    eclp_params_args = get_eclp_params_args(eclp_pool)
    invariant = unscale(eclp_pool.getInvariant())

    # Dbl check invariant
    (
        invariant_expected,
        invariant_expected_err,
    ) = math_implementation.calculateInvariantWithError(
        unscale(rate_scaled_balances), *eclp_params_args
    )
    invariant_expected_vec = (
        invariant_expected + 2 * invariant_expected_err,
        invariant_expected,
    )
    assert invariant == invariant_expected

    amount_out_expected_unscaled = unscale(
        rate_scaled_balances[1]
    ) - math_implementation.calcYGivenX(
        unscale(rate_scaled_balances[0] + amountToSwapMinusFees_ratescaled),
        *eclp_params_args,
        invariant_expected_vec,
    )

    # Backup for later comparison
    spot_price_before_swap = rate_scaled_eclp_pool.getPrice()

    # Triple check math calc. (not needed)
    # sparams, _ = eclp_pool.getECLPParams()
    # mparams = params2MathParams(ECLPMathParams(*unscale(sparams)))
    # eclp = math_implementation_old.ECLP.from_x_y(*unscale(rate_scaled_balances), mparams)
    # amount_out_expected_unscaled2 = -eclp.trade_x(unscale(amountToSwapMinusFees_ratescaled), mock=True)
    # assert amount_out_expected_unscaled2 == amount_out_expected_unscaled.approxed()

    swapRequest = SwapRequest(
        kind=SwapKind.GivenIn,  # SwapKind - GIVEN_IN
        tokenIn=gyro_erc20_funded[0].address,  # IERC20
        tokenOut=gyro_erc20_funded[1].address,  # IERC20
        amount=amount_to_swap,  # uint256
        poolId=poolId,  # bytes32
        lastChangeBlock=0,  # uint256
        from_aux=users[1],  # address
        to=users[1],  # address
        userData=(0).to_bytes(32, "big"),  # bytes
    )

    tx = mock_vault.callMinimalGyroPoolSwap(eclp_pool.address, swapRequest, *balances)

    assert tx.events["Swap"][0]["tokenIn"] == gyro_erc20_funded[0]
    assert tx.events["Swap"][0]["tokenOut"] == gyro_erc20_funded[1]
    amount_out = tx.events["Swap"][0]["amount"]

    # Check against amount without price impact. We should see a nonzero but not huge price impact.
    amount_out_spot_unscaled = unscale(amountToSwapMinusFees) * unscale(
        spot_price_before_swap
    )  # if we had no price impact
    assert unscale(amount_out) < amount_out_spot_unscaled
    assert unscale(amount_out) == amount_out_spot_unscaled.approxed(rel=D("0.05"))

    # Check balances
    (_, balances_after_swap) = mock_vault.getPoolTokens(poolId)
    assert balances_after_swap[0] == balances[0] + amount_to_swap
    assert balances_after_swap[1] == balances[1] - amount_out

    assert unscale(amount_out) == amount_out_expected_unscaled.approxed()

    # Now there are unaccounted-for protocol fees (see conftest: we have protocol fees enabled!)
    actual_supply_after_swap = eclp_pool.getActualSupply()
    assert actual_supply_after_swap > eclp_pool.totalSupply()
    assert eclp_pool.getInvariantDivActualSupply() < get_invariant_div_supply(eclp_pool)

    bpt_tokens_to_redeem = eclp_pool.balanceOf(users[0]) // 2
    tx = mock_vault.callExitPoolGyro(
        eclp_pool.address,
        0,
        users[0],
        users[0],
        mock_vault.getPoolTokens(poolId)[1],
        0,
        0,
        bpt_tokens_to_redeem,
    )
    # Post-exit supply matches pre-exit actual supply, minus tokens burnt in exit, and the two agree again.
    assert eclp_pool.getActualSupply() == eclp_pool.totalSupply()
    assert eclp_pool.getInvariantDivActualSupply() == get_invariant_div_supply(
        eclp_pool
    )
    ev = get_transfer_event(tx, from_addr=users[0])
    bptTokensburnt = ev["value"]
    assert ev["to"] == ZERO_ADDRESS
    assert bptTokensburnt == bpt_tokens_to_redeem
    total_supply_expd = actual_supply_after_swap - bptTokensburnt
    total_supply = eclp_pool.totalSupply()
    assert total_supply == total_supply_expd  # The actual test


def test_pool_factory(mock_rate_scaled_eclp_pool_from_factory):
    """This test does almost nothing but run the creation once to make sure it works."""
    mock_pool_from_factory = mock_rate_scaled_eclp_pool_from_factory
    assert mock_pool_from_factory.name() == "RateScaledGyroECLPTwoPool"
    assert mock_pool_from_factory.symbol() == "RSGCTP"
