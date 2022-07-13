from math import cos, sin, pi
from pprint import pprint

from brownie import (
    accounts,
    GyroCEMMPool,
    GyroCEMMMathTesting,
    GyroCEMMMath,
    MockVault,
    Authorizer,
    MockGyroConfig,
    SimpleERC20,
    Contract,
    QueryProcessor, history,
)
from brownie.network.transaction import TransactionReceipt

from tests.cemm import cemm_prec_implementation
from tests.conftest import scale_cemm_params, scale_derived_values
from tests.support.quantized_decimal import QuantizedDecimal as D
from tests.support.types import CallJoinPoolGyroParams, SwapKind, SwapRequest, TwoPoolBaseParams, CEMMMathParams, \
    CEMMPoolParams

from tests.support.trace_analyzer import Tracer

from tabulate import tabulate

################ Config ###################

# All of these values are unscaled.
from tests.support.utils import scale, unscale

alpha = D("0.97")
beta = D("1.02")
phi_degrees = 45
l_lambda = D("2")

oracleEnabled = False

swapFeePercentage = D('0.1') / D(100)
# protocolSwapFeePercentage = D('0.5') / D(100)
protocolSwapFeePercentage = 0

# The following just has to be large enough
TOKENS_PER_USER = 1000

init_amounts_in = [100, 100]

###########################################

c_phi = D(cos(phi_degrees / 360 * 2 * pi))
s_phi = D(sin(phi_degrees / 360 * 2 * pi))

# MOCK POOL FROM FACTORY
admin = accounts[0]

# For experiments with external library calls. Not normally needed.
# admin.deploy(GyroCEMMMath)

authorizer = admin.deploy(Authorizer, admin)

mock_vault = admin.deploy(MockVault, authorizer)

mock_gyro_config = admin.deploy(MockGyroConfig)

gyro_cemm_math_testing = admin.deploy(GyroCEMMMathTesting)

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

# Not used in code, but needs to be deployed.
admin.deploy(QueryProcessor)

admin.deploy(GyroCEMMMath)

# MOCK POOL

two_pool_base_params = TwoPoolBaseParams(
        vault=mock_vault.address,
        name="GyroCEMMTwoPool",  # string
        symbol="GCTP",  # string
        token0=gyro_erc20_funded[0].address,  # IERC20
        token1=gyro_erc20_funded[1].address,  # IERC20
        swapFeePercentage=swapFeePercentage * 10**18,
        pauseWindowDuration=0,  # uint256
        bufferPeriodDuration=0,  # uint256
        oracleEnabled=oracleEnabled,  # bool
        owner=admin,  # address
    )

cemm_params = CEMMMathParams(
    alpha=alpha,
    beta=beta,
    c=c_phi,
    s=s_phi,
    l=l_lambda,
)
derived_cemm_params = cemm_prec_implementation.calc_derived_values(cemm_params)
args = CEMMPoolParams(
    two_pool_base_params,
    scale_cemm_params(cemm_params),
    scale_derived_values(derived_cemm_params),
)
mock_vault_pool = admin.deploy(
    GyroCEMMPool, args, mock_gyro_config.address, gas_limit=11250000
)

# Set to an integer to only show that deep of traces. Nice to avoid visual overload.
MAXLVL = None

def my_call_trace(tracer: Tracer, tx: TransactionReceipt):
    print(tracer.trace_tx(tx).format(maxlvl=MAXLVL))
    # s: str = repr(tracer.trace_tx(tx))
    # if MAXLVL is not None:
    #     lines = s.splitlines()
    #     if len(lines) > MAXLVL:
    #         lines = lines[:MAXLVL - 1]
    #         s = "\n".join(lines) + "\n [...]"
    #         print(s)
    #         return
    # print(s)

def main():
    poolId = mock_vault_pool.getPoolId()
    (params, derived) = mock_vault_pool.getCEMMParams()

    ##################################################
    ## Add initial liquidity
    ##################################################
    print("----- 1: Join (Initial) -----\n")

    tx_total = mock_vault.callJoinPoolGyro(
        CallJoinPoolGyroParams(
            mock_vault_pool.address,
            poolId,
            users[0],
            users[0],
            (0, 0),   # current balances
            0,
            protocolSwapFeePercentage * 10**18,
            scale(init_amounts_in),
            0,  # amount_out not used for init
        )
    )

    tracer = Tracer.load()

    my_call_trace(tracer, tx_total)
    print()


    ##################################################
    ## Add liqudidity to an already initialized pool
    ##################################################
    print("----- 2: Join (Non-Initial After Initial) -----\n")
    (_, balances) = mock_vault.getPoolTokens(poolId)
    bpt_amount_out = unscale(mock_vault_pool.totalSupply()) * D('0.2')
    tx_total = mock_vault.callJoinPoolGyro(
        CallJoinPoolGyroParams(
            mock_vault_pool.address,
            poolId,
            users[1],
            users[1],
            balances,  # current balances
            0,
            protocolSwapFeePercentage * 10 ** 18,
            [0, 0],  # amounts in not used outside init
            scale(bpt_amount_out),
        )
    )

    my_call_trace(tracer, tx_total)
    print()

    ##################################################
    ## Conduct swaps
    ##################################################
    print("----- 3: Swap (After Join) -----\n")

    (_, balances) = mock_vault.getPoolTokens(poolId)

    amount_to_swap = 10

    swapRequest = SwapRequest(
        kind=SwapKind.GivenIn,  # SwapKind - GIVEN_IN
        tokenIn=gyro_erc20_funded[0].address,  # IERC20
        tokenOut=gyro_erc20_funded[1].address,  # IERC20
        amount=scale(amount_to_swap),  # uint256
        poolId=poolId,  # bytes32
        lastChangeBlock=0,  # uint256
        from_aux=users[1],  # address
        to=users[1],  # address
        userData=(0).to_bytes(32, "big"),  # bytes
    )

    tx_total = mock_vault.callMinimalGyroPoolSwap(
        mock_vault_pool.address,
        swapRequest,
        balances[0],
        balances[1],
    )

    my_call_trace(tracer, tx_total)
    print()

    print("----- 4: Swap (After Swap) -----\n")
    (_, balances) = mock_vault.getPoolTokens(poolId)

    amount_to_swap = 10

    swapRequest = SwapRequest(
        kind=SwapKind.GivenIn,  # SwapKind - GIVEN_IN
        tokenIn=gyro_erc20_funded[0].address,  # IERC20
        tokenOut=gyro_erc20_funded[1].address,  # IERC20
        amount=scale(amount_to_swap),  # uint256
        poolId=poolId,  # bytes32
        lastChangeBlock=0,  # uint256
        from_aux=users[1],  # address
        to=users[1],  # address
        userData=(0).to_bytes(32, "big"),  # bytes
    )

    tx_total = mock_vault.callMinimalGyroPoolSwap(
        mock_vault_pool.address,
        swapRequest,
        balances[0],
        balances[1],
    )

    my_call_trace(tracer, tx_total)
    print()

    ##################################################
    ## Add liqudidity after swap
    ##################################################
    print("----- 5: Join (After Swap) -----\n")

    (_, balances) = mock_vault.getPoolTokens(poolId)
    bpt_amount_out = unscale(mock_vault_pool.totalSupply()) * D('1.2')
    tx_total = mock_vault.callJoinPoolGyro(
        CallJoinPoolGyroParams(
            mock_vault_pool.address,
            poolId,
            users[1],
            users[1],
            balances,  # current balances
            0,
            protocolSwapFeePercentage * 10 ** 18,
            [0, 0],  # amounts in not used outside init
            scale(bpt_amount_out),
        )
    )

    my_call_trace(tracer, tx_total)
    print()

    ##################################################
    ## Another swap
    ##################################################
    print("----- 6: Swap (Again After Join) -----\n")

    (_, balances) = mock_vault.getPoolTokens(poolId)

    amount_to_swap = 10

    swapRequest = SwapRequest(
        kind=SwapKind.GivenIn,  # SwapKind - GIVEN_IN
        tokenIn=gyro_erc20_funded[0].address,  # IERC20
        tokenOut=gyro_erc20_funded[1].address,  # IERC20
        amount=scale(amount_to_swap),  # uint256
        poolId=poolId,  # bytes32
        lastChangeBlock=0,  # uint256
        from_aux=users[1],  # address
        to=users[1],  # address
        userData=(0).to_bytes(32, "big"),  # bytes
    )

    tx_total = mock_vault.callMinimalGyroPoolSwap(
        mock_vault_pool.address,
        swapRequest,
        balances[0],
        balances[1],
    )

    my_call_trace(tracer, tx_total)
    print()

    ##################################################
    ## Exit pool
    ##################################################
    print("----- 7: Exit (After Swap) -----\n")

    (_, balances) = mock_vault.getPoolTokens(poolId)
    bpt_amount_in = unscale(mock_vault_pool.balanceOf(users[0])) * D('0.7')

    tx_total = mock_vault.callExitPoolGyro(
        mock_vault_pool.address,
        0,
        users[0],
        users[0],
        balances,
        0,
        0,
        bpt_amount_in,
    )

    my_call_trace(tracer, tx_total)
    print()
