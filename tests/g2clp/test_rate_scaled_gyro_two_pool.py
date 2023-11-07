import pytest
from brownie import ZERO_ADDRESS, MockRateProvider

import tests.g2clp.math_implementation as math_impl
from tests.support.quantized_decimal import QuantizedDecimal as D
from tests.conftest import TOKENS_PER_USER
from tests.g2clp import constants
from tests.support.types import CallJoinPoolGyroParams, SwapKind, SwapRequest
from tests.support.utils import (
    unscale,
    approxed,
    scale,
    get_transfer_event,
    get_invariant_div_supply,
)

from math import sqrt


# TODO is this actually testing anything? The original was w/ balancer_vault_pool.
def test_pool_reg(mock_vault, rate_scaled_2clp_pool, gyro_erc20_funded):
    poolId = rate_scaled_2clp_pool.getPoolId()

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


def join_pool(
    vault,
    pool_address,
    sender,
    balances,
    amount_in,
    recipient=None,
    pool_id=0,
    protocol_swap_fees=0,
    last_change_block=0,
    amount_out=0,
):
    if recipient is None:
        recipient = sender
    return vault.callJoinPoolGyro(
        CallJoinPoolGyroParams(
            pool_address,
            pool_id,
            sender,
            recipient,
            balances,
            last_change_block,
            protocol_swap_fees,
            [amount_in, amount_in],
            amount_out,
        )
    )


def test_pool_on_initialize(users, rate_scaled_2clp_pool, mock_vault):
    balances = (0, 0)
    amountIn = 100 * 10**18

    tx = join_pool(
        mock_vault, rate_scaled_2clp_pool.address, users[0], balances, amountIn
    )

    poolId = rate_scaled_2clp_pool.getPoolId()

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

    # This is purely a sanity check. The spot price is close to 1, but *not* equal to 1.00 (even in theory) because the price bounds are not symmetric! This is intentional for this test.
    # We multiply by 2.5 b/c we have 1 x = 1.5 x rate-scaled + 1 y
    assert unscale(initial_bpt_tokens) == unscale(D("2.5") * amountIn).approxed(
        rel=D("0.02")
    )

    # Check that the amountIn is now stored in the pool balance
    (_, initial_balances) = mock_vault.getPoolTokens(poolId)
    assert initial_balances[0] == amountIn
    assert initial_balances[1] == amountIn


def test_pool_view_methods(
    users, rate_scaled_2clp_pool, mock_vault, gyro_two_math_testing
):
    balances = (0, 0)
    amountIn = 100 * 10**18

    tx = join_pool(
        mock_vault, rate_scaled_2clp_pool.address, users[0], balances, amountIn
    )

    virtual_params = unscale(rate_scaled_2clp_pool.getVirtualParameters())
    sqrtAlpha, sqrtBeta = unscale(rate_scaled_2clp_pool.getSqrtParameters())
    invariant = unscale(rate_scaled_2clp_pool.getInvariant())

    rate_scaled_balances = rate_scale_balances(
        rate_scaled_2clp_pool, [amountIn, amountIn]
    )
    invariant_math = unscale(
        gyro_two_math_testing.calculateInvariant(
            rate_scaled_balances, scale(sqrtAlpha), scale(sqrtBeta)
        )
    )
    assert invariant == invariant_math

    assert virtual_params[0] == invariant / sqrtBeta
    assert virtual_params[1] == invariant * sqrtAlpha


def test_pool_on_join(users, rate_scaled_2clp_pool, mock_vault, mock_rate_provider):
    ratex = D("1.5")
    mock_rate_provider.mockRate(scale(ratex))

    amount_in = 100 * 10**18
    amount_in_u = float(unscale(amount_in))

    tx = join_pool(
        mock_vault, rate_scaled_2clp_pool.address, users[0], (0, 0), amount_in
    )

    initial_bpt_tokens = tx.events["Transfer"][1]["value"]

    sqrtParams = rate_scaled_2clp_pool.getSqrtParameters()
    sqrtAlpha = sqrtParams[0] / (10**18)
    sqrtBeta = sqrtParams[1] / (10**18)

    # Check pool's invariant after initialization
    currentInvariant = float(unscale(rate_scaled_2clp_pool.getLastInvariant()))
    actualInvariant = sqrt(
        (amount_in_u * float(ratex) + currentInvariant / sqrtBeta)
        * (amount_in_u + currentInvariant * sqrtAlpha)
    )
    assert currentInvariant == pytest.approx(actualInvariant, rel=1e-10, abs=1e-10)

    poolId = rate_scaled_2clp_pool.getPoolId()
    (_, initial_balances) = mock_vault.getPoolTokens(poolId)

    ##################################################
    ## Add liqudidity to an already initialized pool
    ##################################################
    tx = join_pool(
        mock_vault,
        rate_scaled_2clp_pool.address,
        users[1],
        initial_balances,
        amount_in,
        amount_out=rate_scaled_2clp_pool.totalSupply(),
    )

    ## Check Pool balance Change
    assert tx.events["PoolBalanceChanged"]["liquidityProvider"] == users[1]

    assert tx.events["PoolBalanceChanged"]["deltas"] == (amount_in, amount_in)

    ## Check BTP Token minting
    assert tx.events["Transfer"][0]["from"] == ZERO_ADDRESS
    assert tx.events["Transfer"][0]["to"] == users[1]
    bptTokensNew = tx.events["Transfer"][0]["value"]
    assert bptTokensNew > 0
    assert float(bptTokensNew) == pytest.approx(initial_bpt_tokens)
    # ^ NB this only works b/c we use the same amounts. - Which is ok & the right thing to do, it should be relative!

    (_, balancesAfterJoin) = mock_vault.getPoolTokens(poolId)
    assert balancesAfterJoin[0] == amount_in * 2
    assert balancesAfterJoin[1] == amount_in * 2
    balancesAfterJoin_u = [float(unscale(x)) for x in balancesAfterJoin]

    ## Check new pool's invariant
    newInvariant = rate_scaled_2clp_pool.getLastInvariant()
    assert newInvariant > currentInvariant

    currentInvariant = float(unscale(rate_scaled_2clp_pool.getLastInvariant()))
    actualInvariant = sqrt(
        (balancesAfterJoin_u[0] * float(ratex) + currentInvariant / sqrtBeta)
        * (balancesAfterJoin_u[1] + currentInvariant * sqrtAlpha)
    )
    assert currentInvariant == pytest.approx(actualInvariant, rel=1e-10, abs=1e-10)


def test_exit_pool(users, rate_scaled_2clp_pool, mock_vault, mock_rate_provider):
    ratex = D("1.5")
    mock_rate_provider.mockRate(scale(ratex))

    amount_in = 100 * 10**18
    amount_in_u = float(unscale(amount_in))

    tx = join_pool(
        mock_vault, rate_scaled_2clp_pool.address, users[0], (0, 0), amount_in
    )

    poolId = rate_scaled_2clp_pool.getPoolId()
    (_, initial_balances) = mock_vault.getPoolTokens(poolId)
    tx = join_pool(
        mock_vault,
        rate_scaled_2clp_pool.address,
        users[1],
        initial_balances,
        amount_in,
        amount_out=rate_scaled_2clp_pool.totalSupply(),
    )

    amountOut = 5 * 10**18

    total_supply_before_exit = rate_scaled_2clp_pool.totalSupply()
    (_, balances_after_join) = mock_vault.getPoolTokens(poolId)
    invariant_after_join = rate_scaled_2clp_pool.getLastInvariant()

    tx = mock_vault.callExitPoolGyro(
        rate_scaled_2clp_pool.address,
        0,
        users[0],
        users[0],
        balances_after_join,
        0,
        0,
        rate_scaled_2clp_pool.balanceOf(users[0]) * amountOut // amount_in,
    )

    assert unscale(tx.events["PoolBalanceChanged"]["deltas"]) == approxed(
        unscale((amountOut, amountOut))
    )

    (_, balancesAfterExit) = mock_vault.getPoolTokens(poolId)
    assert int(balancesAfterExit[0]) == pytest.approx(
        balances_after_join[0] - amountOut
    )
    assert int(balancesAfterExit[1]) == pytest.approx(
        balances_after_join[1] - amountOut
    )
    balancesAfterExit_u = [float(unscale(x)) for x in balancesAfterExit]

    ## Check BTP Token minting
    assert tx.events["Transfer"][0]["from"] == users[0]
    assert tx.events["Transfer"][0]["to"] == ZERO_ADDRESS
    bptTokensburnt = tx.events["Transfer"][0]["value"]
    assert bptTokensburnt > 0
    # Check that approx. amount of tokens burnt is proportional to the amount of tokens substracted from the pool
    assert float(bptTokensburnt) == pytest.approx(
        total_supply_before_exit * (amountOut / balances_after_join[0])
    )

    sqrt_alpha, sqrtBeta = [
        v / 10**18 for v in rate_scaled_2clp_pool.getSqrtParameters()
    ]

    ## Check new pool's invariant
    invariant_after_exit = rate_scaled_2clp_pool.getLastInvariant()
    invariant_after_exit_u = float(unscale(invariant_after_exit))
    assert invariant_after_join > invariant_after_exit
    invariant = sqrt(
        (float(ratex) * balancesAfterExit_u[0] + invariant_after_exit_u / sqrtBeta)
        * (balancesAfterExit_u[1] + invariant_after_exit_u * sqrt_alpha)
    )
    assert invariant == pytest.approx(invariant_after_exit_u, rel=1e-10, abs=1e-10)


def test_swap(
    users,
    rate_scaled_2clp_pool,
    mock_vault,
    gyro_erc20_funded,
    gyro_two_math_testing,
    mock_rate_provider,
):
    ratex = D("1.5")
    mock_rate_provider.mockRate(scale(ratex))

    amount_in = 100 * 10**18
    amount_in_u = float(unscale(amount_in))

    tx = join_pool(
        mock_vault, rate_scaled_2clp_pool.address, users[0], (0, 0), amount_in
    )

    poolId = rate_scaled_2clp_pool.getPoolId()
    (_, initial_balances) = mock_vault.getPoolTokens(poolId)
    tx = join_pool(
        mock_vault,
        rate_scaled_2clp_pool.address,
        users[1],
        initial_balances,
        amount_in,
        amount_out=rate_scaled_2clp_pool.totalSupply(),
    )

    amount_out = 5 * 10**18

    (_, balances_after_join) = mock_vault.getPoolTokens(poolId)

    tx = mock_vault.callExitPoolGyro(
        rate_scaled_2clp_pool.address,
        0,
        users[0],
        users[0],
        balances_after_join,
        0,
        0,
        rate_scaled_2clp_pool.balanceOf(users[0]) * amount_out // amount_in,
    )

    (_, balances_after_exit) = mock_vault.getPoolTokens(poolId)

    # No swaps have been made so no protocol fees have accrued.
    assert (
        rate_scaled_2clp_pool.getActualSupply() == rate_scaled_2clp_pool.totalSupply()
    )
    assert (
        rate_scaled_2clp_pool.getInvariantDivActualSupply()
        == get_invariant_div_supply(rate_scaled_2clp_pool)
    )

    amount_to_swap = 10 * 10**18
    (
        current_invariant,
        virtual_param_in,
        virtual_param_out,
    ) = rate_scaled_2clp_pool.calculateCurrentValues(*balances_after_exit, True)

    fees = amount_to_swap * (0.1 / 100)
    amountToSwapMinusFees = amount_to_swap - fees
    amount_out_expected = gyro_two_math_testing.calcOutGivenIn(
        int(ratex * balances_after_exit[0]),  # balanceIn,
        balances_after_exit[1],  # balanceOut,
        float(ratex) * amountToSwapMinusFees,  # amountIn,
        virtual_param_in,  # virtualParamIn,
        virtual_param_out,  # virtualParamOut
    )

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

    tx = mock_vault.callMinimalGyroPoolSwap(
        rate_scaled_2clp_pool.address,
        swapRequest,
        balances_after_exit[0],
        balances_after_exit[1],
    )

    assert tx.events["Swap"][0]["tokenIn"] == gyro_erc20_funded[0]
    assert tx.events["Swap"][0]["tokenOut"] == gyro_erc20_funded[1]
    amount_out = tx.events["Swap"][0]["amount"]

    # N.n. true here b/c we initialize the pool (rate-scaled) away from 1.
    # assert amount_out < amount_to_swap

    # Check balances
    (_, balances_after_swap) = mock_vault.getPoolTokens(poolId)
    assert balances_after_swap[0] == balances_after_exit[0] + amount_to_swap
    assert balances_after_swap[1] == balances_after_exit[1] - amount_out

    assert int(amount_out) == pytest.approx(amount_out_expected, abs=1e-10, rel=1e-10)

    # Now there are unaccounted-for protocol fees (see conftest: we have protocol fees enabled!)
    actual_supply_after_swap = rate_scaled_2clp_pool.getActualSupply()
    assert actual_supply_after_swap > rate_scaled_2clp_pool.totalSupply()
    assert (
        rate_scaled_2clp_pool.getInvariantDivActualSupply()
        < get_invariant_div_supply(rate_scaled_2clp_pool)
    )

    bpt_tokens_to_redeem = rate_scaled_2clp_pool.balanceOf(users[0]) // 2
    tx = mock_vault.callExitPoolGyro(
        rate_scaled_2clp_pool.address,
        0,
        users[0],
        users[0],
        mock_vault.getPoolTokens(poolId)[1],
        0,
        0,
        bpt_tokens_to_redeem,
    )
    # Post-exit supply matches pre-exit actual supply, minus tokens burnt in exit, and the two agree again.
    assert (
        rate_scaled_2clp_pool.getActualSupply() == rate_scaled_2clp_pool.totalSupply()
    )
    assert (
        rate_scaled_2clp_pool.getInvariantDivActualSupply()
        == get_invariant_div_supply(rate_scaled_2clp_pool)
    )
    ev = get_transfer_event(tx, from_addr=users[0])
    bptTokensburnt = ev["value"]
    assert ev["to"] == ZERO_ADDRESS
    assert bptTokensburnt == bpt_tokens_to_redeem
    total_supply_expd = actual_supply_after_swap - bptTokensburnt
    total_supply = rate_scaled_2clp_pool.totalSupply()
    assert total_supply == total_supply_expd  # The actual test


def test_pool_factory(rate_scaled_2clp_pool_from_factory):
    """This test does almost nothing but run the creation once to make sure it works."""
    mock_pool_from_factory = rate_scaled_2clp_pool_from_factory
    assert mock_pool_from_factory.name() == "RateScaledGyro2CLPPoolFromFactory"
    assert mock_pool_from_factory.symbol() == "RSG2PF"
