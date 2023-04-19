from brownie import (
    accounts,
    Gyro2CLPPoolFactory,
    Gyro2CLPPool,
    MockVault,
    Authorizer,
    MockGyroConfig,
    SimpleERC20,
    QueryProcessor,
    Contract,
)
from tests.support.quantized_decimal import QuantizedDecimal as D
from tests.support.types import CallJoinPoolGyroParams, SwapKind, SwapRequest
from tests.support.types import TwoPoolFactoryCreateParams


# MOCK POOL FROM FACTORY
admin = accounts[0]

authorizer = admin.deploy(Authorizer, admin)

mock_vault = admin.deploy(MockVault, authorizer)

mock_gyro_config = admin.deploy(MockGyroConfig)

gyro_erc20_0 = admin.deploy(SimpleERC20)
gyro_erc20_1 = admin.deploy(SimpleERC20)
users = (accounts[1], accounts[2], accounts[3])
TOKENS_PER_USER = 1000 * 10**18


gyro_erc20_0.mint(users[0], TOKENS_PER_USER)
gyro_erc20_1.mint(users[0], TOKENS_PER_USER)
gyro_erc20_0.mint(users[1], TOKENS_PER_USER)
gyro_erc20_1.mint(users[1], TOKENS_PER_USER)


def order_erc_tokens(token1, token2):
    if token1.address.lower() < token2.address.lower():
        return (token1, token2)
    else:
        return (token2, token1)


gyro_erc20_funded = order_erc_tokens(gyro_erc20_0, gyro_erc20_1)

deployed_query_processor = admin.deploy(QueryProcessor)

# MOCK POOL FROM FACTORY

factory = admin.deploy(Gyro2CLPPoolFactory, mock_vault, mock_gyro_config.address)

args = TwoPoolFactoryCreateParams(
    name="Gyro2CLPPoolFromFactory",
    symbol="G2PF",
    tokens=[gyro_erc20_funded[i].address for i in range(2)],
    sqrts=[D("0.97") * 10**18, D("1.02") * 10**18],
    swapFeePercentage=D(1) * 10**15,
    owner=admin,
)

tx = factory.create(*args)

mock_vault_pool = Contract.from_abi("Gyro2CLPPool", tx.return_value, Gyro2CLPPool.abi)

# JOIN POOL


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


def main():
    amount_in = 100 * 10**18

    join_pool(mock_vault, mock_vault_pool.address, users[0], (0, 0), amount_in)

    poolId = mock_vault_pool.getPoolId()
    (_, initial_balances) = mock_vault.getPoolTokens(poolId)

    ##################################################
    ## Add liqudidity to an already initialized pool
    ##################################################
    join_pool(
        mock_vault,
        mock_vault_pool.address,
        users[1],
        initial_balances,
        amount_in,
        amount_out=mock_vault_pool.totalSupply(),
    )

    ##################################################
    ## Conduct swaps
    ##################################################

    poolId = mock_vault_pool.getPoolId()

    (_, balances_after_exit) = mock_vault.getPoolTokens(poolId)

    amount_to_swap = 10 * 10**18

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
        mock_vault_pool.address,
        swapRequest,
        balances_after_exit[0],
        balances_after_exit[1],
    )

    ##################################################
    ## Add liqudidity after swap
    ##################################################
    join_pool(
        mock_vault,
        mock_vault_pool.address,
        users[2],
        initial_balances,
        amount_in,
        amount_out=mock_vault_pool.totalSupply(),
    )

    ##################################################
    ## Exit pool
    ##################################################
    (_, balances_after_join) = mock_vault.getPoolTokens(poolId)
    amountOut = 5 * 10**18

    mock_vault.callExitPoolGyro(
        mock_vault_pool.address,
        0,
        users[0],
        users[0],
        balances_after_join,
        0,
        0,
        mock_vault_pool.balanceOf(users[0]) * amountOut // amount_in,
    )
