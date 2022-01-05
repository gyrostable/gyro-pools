import math
from decimal import Decimal, ROUND_FLOOR, getcontext
from collections import namedtuple
from enum import Enum

import pytest


JoinPoolRequest = namedtuple(
    "JoinPoolRequest",
    [
        "assets",  # IAsset[] => address[]
        "maxAmountsIn",  # uint256[]
        "userData",  # bytes
        "fromInternalBalance",  # bool
    ],
)

SwapRequest = namedtuple(
    "SwapRequest",
    [
        "kind",  # SwapKind
        "tokenIn",  # IERC20
        "tokenOut",  # IERC20
        "amount",  # uint256
        "poolId",  # bytes32
        "lastChangeBlock",  # uint256
        "from_aux",  # address
        "to",  # address
        "userData",  # bytes
    ],
)

ToList = namedtuple(
    "ToList",
    [
        "element0",  #
        "element1",
    ],
)

from conftest import gyro_tokensPerUser

numTokens = 2
numUsers = 2
address0 = "0x0000000000000000000000000000000000000000"


def test_empty_erc20s(admin, gyro_erc20_empty):
    for numToken in range(numTokens):
        gyro_erc20_empty[numToken].mint(admin, gyro_tokensPerUser)
        assert gyro_erc20_empty[numToken].totalSupply() == gyro_tokensPerUser


def test_funded_erc20s(users, gyro_erc20_funded):
    for numToken in range(numTokens):
        assert (
            gyro_erc20_funded[numToken].totalSupply() == gyro_tokensPerUser * numUsers
        )
        for numUser in range(numUsers):
            assert (
                gyro_erc20_funded[numToken].balanceOf(users[numUser])
                == gyro_tokensPerUser
            )


def test_pool_reg(admin, users, gyro_pool_testing, gyro_erc20_funded):
    vault = gyro_pool_testing[0]
    gyroPool = gyro_pool_testing[1]

    poolId = gyroPool.getPoolId()

    # Check pool and token registration
    (tokensAddress, balances, lastChangeBlock) = vault.getPoolTokens(poolId)

    for numToken in range(numTokens):
        assert tokensAddress[numToken] == gyro_erc20_funded[numToken].address
        assert balances[numToken] == 0
        assert balances[numToken] == 0

    balances = ToList(
        element0=0,
        element1=0,
    )

    # Initialize Pool => Didnt work due to gas issues


##    vault.JoinPoolTest(poolId, users[0] , users[0], balances, 0, 0,100)


def test_pool(
    admin,
    users,
    gyro_two_math_testing,
    gyro_pool_testing,
    gyro_poolMockVault_testing,
    gyro_erc20_funded,
):
    """Tests a range of interactions with the pool: Initialization, adding liquidity, and swap."""
    vault = gyro_poolMockVault_testing[0]
    gyroPool = gyro_poolMockVault_testing[1]

    poolId = gyroPool.getPoolId()
    ##################################################
    ## Verify GyroTwoPool Constructor
    ##################################################
    assert gyroPool.getSwapFeePercentage() == 1 * 10 ** 15
    assert gyroPool.getNormalizedWeights() == (0.6 * 10 ** 18, 0.4 * 10 ** 18)

    sqrtParams = gyroPool.getSqrtParameters()
    assert sqrtParams[0] == 0.97 * 10 ** 18
    assert sqrtParams[1] == 1.02 * 10 ** 18

    ##################################################
    ## Initialize Pool
    ##################################################

    balances = ToList(
        element0=0,
        element1=0,
    )
    amountIn = 100 * 10 ** 18
    protocolSwapFees = 0
    tx = vault.callJoinPoolGyro(
        gyroPool.address, 0, users[0], users[0], balances, 0, protocolSwapFees, amountIn
    )

    ## Check Pool balance change
    assert tx.events["PoolBalanceChanged"]["poolId"] == poolId
    assert tx.events["PoolBalanceChanged"]["liquidityProvider"] == users[0]

    assert tx.events["PoolBalanceChanged"]["deltas"] == ToList(
        element0=amountIn,
        element1=amountIn,
    )
    assert tx.events["PoolBalanceChanged"]["protocolFees"] == ToList(
        element0=0,
        element1=0,
    )

    ## Check BPT Token minting
    assert tx.events["Transfer"][1]["from"] == address0
    assert tx.events["Transfer"][1]["to"] == users[0]
    bptTokensInit = tx.events["Transfer"][1]["value"]
    assert bptTokensInit > 0

    ## Check that the amountIn is now stored in the pool balance
    (_, IniBalances) = vault.getPoolTokens(poolId)
    assert IniBalances[0] == amountIn
    assert IniBalances[1] == amountIn
    # TODO make these amounts asymmetric everywhere

    sqrtAlpha = sqrtParams[0] / (10 ** 18)
    sqrtBeta = sqrtParams[1] / (10 ** 18)

    ## Check pool's invariant after initialization
    currentInvariant = gyroPool.getLastInvariant()
    squareInvariant = (amountIn + currentInvariant / sqrtBeta) * (
        amountIn + currentInvariant * sqrtAlpha
    )
    actualSquareInvariant = currentInvariant * currentInvariant
    assert squareInvariant == pytest.approx(actualSquareInvariant)

    ##################################################
    ## Add liqudidity to an already initialized pool
    ##################################################
    tx = vault.callJoinPoolGyro(
        gyroPool.address,
        0,
        users[1],
        users[1],
        IniBalances,
        0,
        protocolSwapFees,
        amountIn,
    )

    ## Check Pool balance Change
    assert tx.events["PoolBalanceChanged"]["liquidityProvider"] == users[1]

    assert tx.events["PoolBalanceChanged"]["deltas"] == ToList(
        element0=amountIn,
        element1=amountIn,
    )

    ## Check BTP Token minting
    assert tx.events["Transfer"][0]["from"] == address0
    assert tx.events["Transfer"][0]["to"] == users[1]
    bptTokensNew = tx.events["Transfer"][0]["value"]
    assert bptTokensNew > 0
    assert float(bptTokensNew) == pytest.approx(bptTokensInit)
    # ^ NB this only works b/c we use the same amounts. - Which is ok & the right thing to do, it should be relative!

    (_, balancesAfterJoin) = vault.getPoolTokens(poolId)
    assert balancesAfterJoin[0] == amountIn * 2
    assert balancesAfterJoin[1] == amountIn * 2

    ## Check new pool's invariant
    newInvariant = gyroPool.getLastInvariant()
    assert newInvariant > currentInvariant

    currentInvariant = gyroPool.getLastInvariant()
    squareInvariant = (balancesAfterJoin[0] + currentInvariant / sqrtBeta) * (
        balancesAfterJoin[1] + currentInvariant * sqrtAlpha
    )
    actualSquareInvariant = currentInvariant * currentInvariant
    assert squareInvariant == pytest.approx(actualSquareInvariant)

    ##################################################
    ## Exit pool
    ##################################################
    amountOut = 5 * 10 ** 18

    totalSupplyBeforeExit = gyroPool.totalSupply()

    tx = vault.callExitPoolGyro(
        gyroPool.address,
        0,
        users[0],
        users[0],
        balancesAfterJoin,
        0,
        protocolSwapFees,
        amountOut,
    )

    assert tx.events["PoolBalanceChanged"]["deltas"] == ToList(
        element0=amountOut,
        element1=amountOut,
    )

    (_, balancesAfterExit) = vault.getPoolTokens(poolId)
    assert balancesAfterExit[0] == balancesAfterJoin[0] - amountOut
    assert balancesAfterExit[1] == balancesAfterJoin[1] - amountOut

    ## Check BTP Token minting
    assert tx.events["Transfer"][0]["from"] == users[0]
    assert tx.events["Transfer"][0]["to"] == address0
    bptTokensburnt = tx.events["Transfer"][0]["value"]
    assert bptTokensburnt > 0
    # Check that approx. amount of tokens burnt is proportional to the amount of tokens substracted from the pool
    assert float(bptTokensburnt) == pytest.approx(
        totalSupplyBeforeExit * (amountOut / balancesAfterJoin[0])
    )

    ## Check new pool's invariant
    invariantAfterExit = gyroPool.getLastInvariant()
    assert newInvariant > invariantAfterExit
    squareInvariant = (balancesAfterExit[0] + invariantAfterExit / sqrtBeta) * (
        balancesAfterExit[1] + invariantAfterExit * sqrtAlpha
    )
    actualSquareInvariant = invariantAfterExit * invariantAfterExit
    assert squareInvariant == pytest.approx(actualSquareInvariant)

    ##################################################
    ## Swap
    ##################################################
    amountToSwap = 10 * 10 ** 18
    (
        currentInvariant,
        virtualParamIn,
        virtualParamOut,
    ) = gyroPool.calculateCurrentValues(
        balancesAfterExit[0], balancesAfterExit[1], True
    )

    fees = amountToSwap * (0.1 / 100)
    amountToSwapMinusFees = amountToSwap - fees
    amountOutExpected = gyro_two_math_testing.calcOutGivenIn(
        balancesAfterExit[0],  # balanceIn,
        balancesAfterExit[1],  # balanceOut,
        amountToSwapMinusFees,  # amountIn,
        virtualParamIn,  # virtualParamIn,
        virtualParamOut,  # virtualParamOut,
        currentInvariant,  # currentInvariant
    )

    swapRequest = SwapRequest(
        kind=0,  # SwapKind - GIVEN_IN
        tokenIn=gyro_erc20_funded[0].address,  # IERC20
        tokenOut=gyro_erc20_funded[1].address,  # IERC20
        amount=amountToSwap,  # uint256
        poolId=poolId,  # bytes32
        lastChangeBlock=0,  # uint256
        from_aux=users[1],  # address
        to=users[1],  # address
        userData=0,  # bytes
    )
    tx = vault.callMinimalGyroPoolSwap(
        gyroPool.address, swapRequest, balancesAfterExit[0], balancesAfterExit[1]
    )

    assert tx.events["Swap"][0]["tokenIn"] == gyro_erc20_funded[0]
    assert tx.events["Swap"][0]["tokenOut"] == gyro_erc20_funded[1]
    amountOut = tx.events["Swap"][0]["amount"]

    assert amountOut < amountToSwap

    # Check balances
    (_, balancesAfterSwap) = vault.getPoolTokens(poolId)
    assert balancesAfterSwap[0] == balancesAfterExit[0] + amountToSwap
    assert balancesAfterSwap[1] == balancesAfterExit[1] - amountOut

    assert float(amountOut) == pytest.approx(amountOutExpected)
