from collections import namedtuple

import pytest
from tests.conftest import TOKENS_PER_USER

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


NUM_TOKENS = 2
NUM_USERS = 2
ADDRESS_0 = "0x0000000000000000000000000000000000000000"


def test_empty_erc20s(admin, gyro_erc20_empty):
    for token in range(NUM_TOKENS):
        gyro_erc20_empty[token].mint(admin, TOKENS_PER_USER)
        assert gyro_erc20_empty[token].totalSupply() == TOKENS_PER_USER


def test_funded_erc20s(users, gyro_erc20_funded):
    for token in range(NUM_TOKENS):
        assert (
            gyro_erc20_funded[token].totalSupply(
            ) == TOKENS_PER_USER * NUM_USERS
        )
        for user in range(NUM_USERS):
            assert (
                gyro_erc20_funded[token].balanceOf(users[user])
                == TOKENS_PER_USER
            )


def test_pool_reg(vault, pool, gyro_erc20_funded):
    poolId = pool.getPoolId()

    # Check pool and token registration
    (tokensAddress, balances) = vault.getPoolTokens(poolId)

    for token in range(NUM_TOKENS):
        assert tokensAddress[token] == gyro_erc20_funded[token].address
        assert balances[token] == 0
        assert balances[token] == 0

    balances = ToList(
        element0=0,
        element1=0,
    )


def test_pool_constructor(vault, pool):
    assert pool.getSwapFeePercentage() == 1 * 10 ** 15
    assert pool.getNormalizedWeights() == (0.6 * 10 ** 18, 0.4 * 10 ** 18)

    sqrtParams = pool.getSqrtParameters()
    assert sqrtParams[0] == 0.97 * 10 ** 18
    assert sqrtParams[1] == 1.02 * 10 ** 18


def test_pool_on_initialize(
        users,
        vault,
        pool):

    balances = ToList(
        element0=0,
        element1=0,
    )
    amountIn = 100 * 10 ** 18
    protocolSwapFees = 0

    # tx = vault.callJoinPoolGyro(
    #     pool.address, 0, users[0], users[0], balances, 0, protocolSwapFees, amountIn
    # )

    # poolId = pool.getPoolId()

    # # Check Pool balance change
    # assert tx.events["PoolBalanceChanged"]["poolId"] == poolId
    # assert tx.events["PoolBalanceChanged"]["liquidityProvider"] == users[0]

    # assert tx.events["PoolBalanceChanged"]["deltas"] == ToList(
    #     element0=amountIn,
    #     element1=amountIn,
    # )
    # assert tx.events["PoolBalanceChanged"]["protocolFees"] == ToList(
    #     element0=0,
    #     element1=0,
    # )

    # # Check BPT Token minting
    # assert tx.events["Transfer"][1]["from"] == ADDRESS_0
    # assert tx.events["Transfer"][1]["to"] == users[0]
    # bptTokensInit = tx.events["Transfer"][1]["value"]
    # assert bptTokensInit > 0

    # # Check that the amountIn is now stored in the pool balance
    # (_, IniBalances) = vault.getPoolTokens(poolId)
    # assert IniBalances[0] == amountIn
    # assert IniBalances[1] == amountIn
    # # TODO make these amounts asymmetric everywhere

    # sqrtParams = pool.getSqrtParameters()
    # sqrtAlpha = sqrtParams[0] / (10 ** 18)
    # sqrtBeta = sqrtParams[1] / (10 ** 18)

    # # Check pool's invariant after initialization
    # currentInvariant = pool.getLastInvariant()
    # squareInvariant = (amountIn + currentInvariant / sqrtBeta) * (
    #     amountIn + currentInvariant * sqrtAlpha
    # )
    # actualSquareInvariant = currentInvariant * currentInvariant
    # assert squareInvariant == pytest.approx(actualSquareInvariant)

#     ##################################################
#     ## Add liqudidity to an already initialized pool
#     ##################################################
#     tx = vault.callJoinPoolGyro(
#         pool.address,
#         0,
#         users[1],
#         users[1],
#         IniBalances,
#         0,
#         protocolSwapFees,
#         amountIn,
#     )

#     ## Check Pool balance Change
#     assert tx.events["PoolBalanceChanged"]["liquidityProvider"] == users[1]

#     assert tx.events["PoolBalanceChanged"]["deltas"] == ToList(
#         element0=amountIn,
#         element1=amountIn,
#     )

#     ## Check BTP Token minting
#     assert tx.events["Transfer"][0]["from"] == ADDRESS_0
#     assert tx.events["Transfer"][0]["to"] == users[1]
#     bptTokensNew = tx.events["Transfer"][0]["value"]
#     assert bptTokensNew > 0
#     assert float(bptTokensNew) == pytest.approx(bptTokensInit)
#     # ^ NB this only works b/c we use the same amounts. - Which is ok & the right thing to do, it should be relative!

#     (_, balancesAfterJoin) = vault.getPoolTokens(poolId)
#     assert balancesAfterJoin[0] == amountIn * 2
#     assert balancesAfterJoin[1] == amountIn * 2

#     ## Check new pool's invariant
#     newInvariant = pool.getLastInvariant()
#     assert newInvariant > currentInvariant

#     currentInvariant = pool.getLastInvariant()
#     squareInvariant = (balancesAfterJoin[0] + currentInvariant / sqrtBeta) * (
#         balancesAfterJoin[1] + currentInvariant * sqrtAlpha
#     )
#     actualSquareInvariant = currentInvariant * currentInvariant
#     assert squareInvariant == pytest.approx(actualSquareInvariant)

#     ##################################################
#     ## Exit pool
#     ##################################################
#     amountOut = 5 * 10 ** 18

#     totalSupplyBeforeExit = pool.totalSupply()

#     tx = vault.callExitPoolGyro(
#         pool.address,
#         0,
#         users[0],
#         users[0],
#         balancesAfterJoin,
#         0,
#         protocolSwapFees,
#         amountOut,
#     )

#     assert tx.events["PoolBalanceChanged"]["deltas"] == ToList(
#         element0=amountOut,
#         element1=amountOut,
#     )

#     (_, balancesAfterExit) = vault.getPoolTokens(poolId)
#     assert balancesAfterExit[0] == balancesAfterJoin[0] - amountOut
#     assert balancesAfterExit[1] == balancesAfterJoin[1] - amountOut

#     ## Check BTP Token minting
#     assert tx.events["Transfer"][0]["from"] == users[0]
#     assert tx.events["Transfer"][0]["to"] == ADDRESS_0
#     bptTokensburnt = tx.events["Transfer"][0]["value"]
#     assert bptTokensburnt > 0
#     # Check that approx. amount of tokens burnt is proportional to the amount of tokens substracted from the pool
#     assert float(bptTokensburnt) == pytest.approx(
#         totalSupplyBeforeExit * (amountOut / balancesAfterJoin[0])
#     )

#     ## Check new pool's invariant
#     invariantAfterExit = pool.getLastInvariant()
#     assert newInvariant > invariantAfterExit
#     squareInvariant = (balancesAfterExit[0] + invariantAfterExit / sqrtBeta) * (
#         balancesAfterExit[1] + invariantAfterExit * sqrtAlpha
#     )
#     actualSquareInvariant = invariantAfterExit * invariantAfterExit
#     assert squareInvariant == pytest.approx(actualSquareInvariant)

#     ##################################################
#     ## Swap
#     ##################################################
#     amountToSwap = 10 * 10 ** 18
#     (
#         currentInvariant,
#         virtualParamIn,
#         virtualParamOut,
#     ) = pool.calculateCurrentValues(
#         balancesAfterExit[0], balancesAfterExit[1], True
#     )

#     fees = amountToSwap * (0.1 / 100)
#     amountToSwapMinusFees = amountToSwap - fees
#     amountOutExpected = gyro_two_math_testing.calcOutGivenIn(
#         balancesAfterExit[0],  # balanceIn,
#         balancesAfterExit[1],  # balanceOut,
#         amountToSwapMinusFees,  # amountIn,
#         virtualParamIn,  # virtualParamIn,
#         virtualParamOut,  # virtualParamOut,
#         currentInvariant,  # currentInvariant
#     )

#     swapRequest = SwapRequest(
#         kind=0,  # SwapKind - GIVEN_IN
#         tokenIn=gyro_erc20_funded[0].address,  # IERC20
#         tokenOut=gyro_erc20_funded[1].address,  # IERC20
#         amount=amountToSwap,  # uint256
#         poolId=poolId,  # bytes32
#         lastChangeBlock=0,  # uint256
#         from_aux=users[1],  # address
#         to=users[1],  # address
#         userData=0,  # bytes
#     )
#     tx = vault.callMinimalpoolSwap(
#         pool.address, swapRequest, balancesAfterExit[0], balancesAfterExit[1]
#     )

#     assert tx.events["Swap"][0]["tokenIn"] == gyro_erc20_funded[0]
#     assert tx.events["Swap"][0]["tokenOut"] == gyro_erc20_funded[1]
#     amountOut = tx.events["Swap"][0]["amount"]

#     assert amountOut < amountToSwap

#     # Check balances
#     (_, balancesAfterSwap) = vault.getPoolTokens(poolId)
#     assert balancesAfterSwap[0] == balancesAfterExit[0] + amountToSwap
#     assert balancesAfterSwap[1] == balancesAfterExit[1] - amountOut

#     assert float(amountOut) == pytest.approx(amountOutExpected)
