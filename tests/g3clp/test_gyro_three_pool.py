from math import prod

import pytest
from brownie import ZERO_ADDRESS
from tests.conftest import TOKENS_PER_USER
from tests.g3clp import constants
from tests.support.types import CallJoinPoolGyroParams, SwapKind, SwapRequest
from tests.support.quantized_decimal import QuantizedDecimal as D
from tests.support.utils import (
    unscale,
    scale,
    approxed,
    to_decimal,
    get_transfer_event,
    get_invariant_div_supply,
)


def test_empty_erc20s(admin, gyro_erc20_empty3):
    for token in range(constants.NUM_TOKENS):
        gyro_erc20_empty3[token].mint(admin, TOKENS_PER_USER)
        assert gyro_erc20_empty3[token].totalSupply() == TOKENS_PER_USER


def test_funded_erc20s(users, gyro_erc20_funded3):
    for token in range(constants.NUM_TOKENS):
        assert (
            gyro_erc20_funded3[token].totalSupply()
            == TOKENS_PER_USER * constants.NUM_USERS
        )
        for user in range(constants.NUM_USERS):
            assert gyro_erc20_funded3[token].balanceOf(users[user]) == TOKENS_PER_USER


def test_pool_reg(balancer_vault, balancer_vault_pool3, gyro_erc20_funded3):
    poolId = balancer_vault_pool3.getPoolId()

    # Check pool and token registration
    (token_addresses, token_balances, last_change_block) = balancer_vault.getPoolTokens(
        poolId
    )

    for token in range(constants.NUM_TOKENS):
        assert token_addresses[token] == gyro_erc20_funded3[token].address
        assert token_balances[token] == 0


def test_pool_constructor(mock_vault_pool3):
    assert mock_vault_pool3.getSwapFeePercentage() == 1 * 10**15
    assert mock_vault_pool3.getRoot3Alpha() == D("0.97") * 10**18


def test_pool_factory(mock_pool3_from_factory):
    assert mock_pool3_from_factory.name() == "Gyro3CLPPoolFromFactory"
    assert mock_pool3_from_factory.symbol() == "G3PF"
    assert mock_pool3_from_factory.getRoot3Alpha() == D("0.97") * 10**18
    assert mock_pool3_from_factory.getSwapFeePercentage() == D(1) * 10**15


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
            [amount_in] * 3,
            amount_out,
        )
    )


@pytest.mark.parametrize("amountIn", [100 * 10**18, 10**11 * 10**18])
# Note that a pool initialized with assets of 1e11 (= max assets) couldn't be swapped against. So this is really a theoretical upper bound.
def test_pool_on_initialize(users, mock_vault_pool3, mock_vault, amountIn):
    balances = (0, 0, 0)

    tx = join_pool(mock_vault, mock_vault_pool3.address, users[0], balances, amountIn)

    poolId = mock_vault_pool3.getPoolId()

    # Check Pool balance change
    assert tx.events["PoolBalanceChanged"]["poolId"] == poolId
    assert tx.events["PoolBalanceChanged"]["liquidityProvider"] == users[0]

    assert tx.events["PoolBalanceChanged"]["deltas"] == (amountIn, amountIn, amountIn)
    assert tx.events["PoolBalanceChanged"]["protocolFees"] == (0, 0, 0)

    # Check BPT Token minting
    assert tx.events["Transfer"][1]["from"] == ZERO_ADDRESS
    assert tx.events["Transfer"][1]["to"] == users[0]
    initial_bpt_tokens = tx.events["Transfer"][1]["value"]
    assert initial_bpt_tokens > 0

    # Since the 3CLP always has symmetric price bounds and we've initialized it with equal balances, this check should come out rather precisely.
    assert unscale(initial_bpt_tokens) == unscale(3 * amountIn).approxed(
        abs=to_decimal("1e-10")
    )

    # Check that the amountIn is now stored in the pool balance
    (_, initial_balances) = mock_vault.getPoolTokens(poolId)
    initial_balances = tuple(initial_balances)
    assert initial_balances == (amountIn, amountIn, amountIn)


@pytest.mark.parametrize("amountIn", [100 * 10**18, 10**11 * 10**18])
def test_pool_view_methods(
    users, mock_vault_pool3, mock_vault, amountIn, gyro_three_math_testing
):
    balances = (0, 0)

    tx = join_pool(mock_vault, mock_vault_pool3.address, users[0], balances, amountIn)

    invariant = unscale(mock_vault_pool3.getInvariant())
    root3Alpha = unscale(mock_vault_pool3.getRoot3Alpha())
    invariant_math = unscale(
        gyro_three_math_testing.calculateInvariant(
            [amountIn, amountIn, amountIn],
            scale(root3Alpha),
        )
    )
    assert invariant == invariant_math


@pytest.mark.parametrize("amount_in", [100 * 10**18, 5 * 10**10 * 10**18])
# Note that for the second (large) test case, the join (of size = init size) completely fills up the pool.
def test_pool_on_join(users, mock_vault_pool3, mock_vault, amount_in):
    ##################################################
    ## Initialize pool
    ##################################################
    tx = join_pool(mock_vault, mock_vault_pool3.address, users[0], (0, 0, 0), amount_in)

    initial_bpt_tokens = tx.events["Transfer"][1]["value"]

    root3Alpha = unscale(mock_vault_pool3.getRoot3Alpha())

    # Check pool's invariant after initialization
    currentInvariant = unscale(mock_vault_pool3.getLastInvariant())
    cubeInvariant_calcd = (unscale(amount_in) + currentInvariant * root3Alpha) ** 3
    cubeInvariant_pool = currentInvariant**3

    # Approximation is rough here, see the math tests for more fine-grained comparisons.
    assert cubeInvariant_calcd == cubeInvariant_pool.approxed()

    poolId = mock_vault_pool3.getPoolId()
    (_, initial_balances) = mock_vault.getPoolTokens(poolId)

    ##################################################
    ## Add liqudidity to an already initialized pool
    ##################################################
    tx = join_pool(
        mock_vault,
        mock_vault_pool3.address,
        users[1],
        initial_balances,
        0,  # Not used
        amount_out=mock_vault_pool3.totalSupply(),  # say...
    )

    ## Check Pool balance Change
    assert tx.events["PoolBalanceChanged"]["liquidityProvider"] == users[1]

    assert tx.events["PoolBalanceChanged"]["deltas"] == (
        amount_in,
        amount_in,
        amount_in,
    )

    ## Check BPT Token minting
    assert tx.events["Transfer"][0]["from"] == ZERO_ADDRESS
    assert tx.events["Transfer"][0]["to"] == users[1]
    bptTokensNew = tx.events["Transfer"][0]["value"]
    assert bptTokensNew > 0
    assert float(bptTokensNew) == pytest.approx(initial_bpt_tokens)
    # ^ NB this only works b/c we use the same amounts. - Which is ok & the right thing to do, it should be relative!

    (_, balancesAfterJoin) = mock_vault.getPoolTokens(poolId)
    assert balancesAfterJoin[0] == amount_in * 2
    assert balancesAfterJoin[1] == amount_in * 2
    assert balancesAfterJoin[2] == amount_in * 2

    ## Check new pool's invariant
    newInvariant = mock_vault_pool3.getLastInvariant()
    assert newInvariant > currentInvariant

    currentInvariant = unscale(mock_vault_pool3.getLastInvariant())
    cubeInvariant_calcd = prod(
        unscale(balancesAfterJoin[i]) + currentInvariant * root3Alpha for i in range(3)
    )
    cubeInvariant_pool = currentInvariant**3
    assert cubeInvariant_calcd == cubeInvariant_pool.approxed()


@pytest.mark.parametrize(
    ("amount_in", "amountOut"),
    [
        (scale(100), scale(5)),
        (scale("0.5e11"), scale("0.499e11")),
    ],
)
# ^ NB We join twice here (first init, then normal join with another account)
def test_pool_on_exit(users, mock_vault_pool3, mock_vault, amount_in, amountOut):
    ## Initialize Pool
    tx = join_pool(mock_vault, mock_vault_pool3.address, users[0], (0, 0, 0), amount_in)

    poolId = mock_vault_pool3.getPoolId()
    (_, initial_balances) = mock_vault.getPoolTokens(poolId)
    tx = join_pool(
        mock_vault,
        mock_vault_pool3.address,
        users[1],
        initial_balances,
        0,  # Not used
        amount_out=mock_vault_pool3.totalSupply(),  # say...
    )

    total_supply_before_exit = mock_vault_pool3.totalSupply()
    (_, balances_after_exit) = mock_vault.getPoolTokens(poolId)
    invariant_before_exit = mock_vault_pool3.getLastInvariant()

    print(mock_vault_pool3.balanceOf(users[0]))

    tx = mock_vault.callExitPoolGyro(
        mock_vault_pool3.address,
        poolId,
        users[0],
        users[0],
        balances_after_exit,
        0,
        0,
        (
            to_decimal(mock_vault_pool3.balanceOf(users[0])) * amountOut / amount_in
        ).floor(),
    )

    assert unscale(tx.events["PoolBalanceChanged"]["deltas"]) == approxed(
        unscale((amountOut, amountOut, amountOut))
    )

    (_, balancesAfterExit) = mock_vault.getPoolTokens(poolId)
    assert int(balancesAfterExit[0]) == pytest.approx(
        balances_after_exit[0] - amountOut
    )
    assert int(balancesAfterExit[1]) == pytest.approx(
        balances_after_exit[1] - amountOut
    )
    assert int(balancesAfterExit[2]) == pytest.approx(
        balances_after_exit[2] - amountOut
    )

    ## Check BTP Token burning
    assert tx.events["Transfer"][0]["from"] == users[0]
    assert tx.events["Transfer"][0]["to"] == ZERO_ADDRESS
    bptTokensburnt = tx.events["Transfer"][0]["value"]
    assert bptTokensburnt > 0
    # Check that approx. amount of tokens burnt is proportional to the amount of tokens substracted from the pool
    assert (
        to_decimal(bptTokensburnt)
        == (
            to_decimal(total_supply_before_exit)
            * (to_decimal(amountOut) / to_decimal(balances_after_exit[0]))
        ).approxed()
    )

    root3Alpha = unscale(mock_vault_pool3.getRoot3Alpha())

    ## Check new pool's invariant
    currentInvariant = unscale(mock_vault_pool3.getLastInvariant())
    cubeInvariant_calcd = prod(
        unscale(balancesAfterExit[i]) + currentInvariant * root3Alpha for i in range(3)
    )
    cubeInvariant_pool = currentInvariant**3
    assert cubeInvariant_calcd == cubeInvariant_pool.approxed()

    assert currentInvariant < invariant_before_exit


@pytest.mark.parametrize(
    ("amount_in", "amount_to_swap"),
    [(scale(100), scale(10)), (scale("0.355e11"), scale("0.29e11"))],
)
# ^ NB We join twice here (first init, then normal join with another account)
def test_swap(
    users,
    mock_vault_pool3,
    mock_vault,
    gyro_erc20_funded3,
    gyro_three_math_testing,
    amount_in,
    amount_to_swap,
):
    ## Initialize
    tx = join_pool(mock_vault, mock_vault_pool3.address, users[0], (0, 0, 0), amount_in)

    poolId = mock_vault_pool3.getPoolId()
    (_, initial_balances) = mock_vault.getPoolTokens(poolId)
    tx = join_pool(
        mock_vault,
        mock_vault_pool3.address,
        users[1],
        initial_balances,
        amount_in,
        amount_out=mock_vault_pool3.totalSupply(),
    )

    (_, balances) = mock_vault.getPoolTokens(poolId)

    root3Alpha = unscale(mock_vault_pool3.getRoot3Alpha())
    current_invariant = unscale(mock_vault_pool3.getLastInvariant())

    fees = amount_to_swap * (D("0.1") / 100)
    amountToSwapMinusFees = (amount_to_swap - fees).floor()

    amount_out_expected = gyro_three_math_testing.calcOutGivenIn(
        balances[0],  # balanceIn,
        balances[1],  # balanceOut,
        amountToSwapMinusFees,  # amountIn,
        scale(current_invariant * root3Alpha),  # virtualOffsetInOut
    )

    # No swaps have been made so no protocol fees have accrued.
    assert mock_vault_pool3.getActualSupply() == mock_vault_pool3.totalSupply()
    assert mock_vault_pool3.getInvariantDivActualSupply() == get_invariant_div_supply(
        mock_vault_pool3
    )

    swapRequest = SwapRequest(
        kind=SwapKind.GivenIn,  # SwapKind - GIVEN_IN
        tokenIn=gyro_erc20_funded3[0].address,  # IERC20
        tokenOut=gyro_erc20_funded3[1].address,  # IERC20
        amount=amount_to_swap,  # uint256
        poolId=poolId,  # bytes32
        lastChangeBlock=0,  # uint256
        from_aux=users[1],  # address
        to=users[1],  # address
        userData=(0).to_bytes(32, "big"),  # bytes
    )

    tx = mock_vault.callMinimalGyroPoolSwap(
        mock_vault_pool3.address,
        swapRequest,
        balances[0],
        balances[1],
    )

    assert tx.events["Swap"][0]["tokenIn"] == gyro_erc20_funded3[0]
    assert tx.events["Swap"][0]["tokenOut"] == gyro_erc20_funded3[1]
    amount_out = tx.events["Swap"][0]["amount"]

    assert amount_out < amount_to_swap
    # ^ B/c (1) initial price was 1, and we have some price impact; (2) fees

    # Check balances
    (_, balances_after_swap) = mock_vault.getPoolTokens(poolId)
    assert balances_after_swap[0] == balances[0] + amount_to_swap
    assert balances_after_swap[1] == balances[1] - amount_out
    assert balances_after_swap[2] == balances[2]

    assert unscale(amount_out) == approxed(unscale(amount_out_expected))

    # Now there are unaccounted-for protocol fees (see conftest: we have protocol fees enabled!)
    actual_supply_after_swap = mock_vault_pool3.getActualSupply()
    assert actual_supply_after_swap > mock_vault_pool3.totalSupply()
    assert mock_vault_pool3.getInvariantDivActualSupply() < get_invariant_div_supply(
        mock_vault_pool3
    )

    bpt_tokens_to_redeem = mock_vault_pool3.balanceOf(users[0]) // 2
    assert bpt_tokens_to_redeem > 0
    tx = mock_vault.callExitPoolGyro(
        mock_vault_pool3.address,
        0,
        users[0],
        users[0],
        mock_vault.getPoolTokens(poolId)[1],
        0,
        0,
        bpt_tokens_to_redeem,
    )
    # Post-exit supply matches pre-exit actual supply, minus tokens burnt in exit, and the two agree again.
    assert mock_vault_pool3.getActualSupply() == mock_vault_pool3.totalSupply()
    assert mock_vault_pool3.getInvariantDivActualSupply() == get_invariant_div_supply(
        mock_vault_pool3
    )
    ev = get_transfer_event(tx, from_addr=users[0])
    bptTokensburnt = ev["value"]
    assert ev["to"] == ZERO_ADDRESS
    assert bptTokensburnt == bpt_tokens_to_redeem
    total_supply_expd = actual_supply_after_swap - bptTokensburnt
    total_supply = mock_vault_pool3.totalSupply()
    assert total_supply == total_supply_expd  # The actual test
