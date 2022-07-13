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

def gas_without_call_cost(tx: TransactionReceipt):
    return tx.gas_used - call_cost(tx)

def call_cost(tx: TransactionReceipt):
    """This is 21-24k but actually hard to compute exactly because of (...). We pull out an internal variable computed in (e.g.) call_trace().

    See: https://github.com/eth-brownie/brownie/blob/c01ff902f3586d31f07610bb9e6261886135a3e1/brownie/network/transaction.py#L830"""
    tx._expand_trace()
    return tx._call_cost


def tracer_events2call_tree(tx: TransactionReceipt):
    """
    Collects DebugGasTracer events and transforms them into a call tree with gas costs.

    Returns: A tree of dicts with keys:
    - subcalls: list
    - fn: str
    - gas_used: int = total gas used by context (including the events themselves!)
    - gas_subcalls: int = total gas used by subcalls. gas_subcalls ≤ gas_used
    """
    # Build tree structure into 'cur'
    stack = [dict(subcalls=[])]  # Top = Synthetic stack frame. The only one without enter/exit events.
    for ev in tx.events['DebugGasTracer']:
        if ev['isEnter']:
            stack.append(dict(subcalls=[], ev_enter=ev))
        else:
            call = stack.pop()  # Fails if there's an exit without an enter event.
            assert call['ev_enter']['fn'] == ev['fn']  # Fails when enter/exit events are mismatched.
            call['ev_leave'] = ev
            stack[-1]['subcalls'].append(call)

    (top,) = stack  # Fails if there's an enter without an exit event.

    # Process tree and add annotations
    def go(call: dict):
        if 'ev_enter' in call and 'ev_leave' in call:
            call['gas_used'] = call['ev_enter']['gasleft'] - call['ev_leave']['gasleft']
            call['fn'] = call['ev_enter']['fn']

            # Events not needed anymore and tend to clutter debug output
            del call['ev_enter'], call['ev_leave']
        else:
            # Synthetic toplevel frame, represents the whole tx. Use its gas minus call cost.
            call['gas_used'] = gas_without_call_cost(tx)
            call['fn'] = 'TOP'

        # Preorder matters!
        for c in call['subcalls']:
            go(c)
        call['gas_subcalls'] = sum(c['gas_used'] for c in call['subcalls'])

    go(top)
    return top


def print_call_tree(call: dict):
    """call: Output of tracer_events2call_tree"""
    indentstr = "   "
    gasfmt = "{:_}"

    def go(call: dict, lvl: int):
        gas_inner = call['gas_used'] - call['gas_subcalls']
        line = "".join([
            indentstr * lvl,
            " " if lvl > 0 else "",
            call['fn'],
            " ",
            "[", gasfmt.format(gas_inner), " / ", gasfmt.format(call['gas_used']), "]"
        ])

        print(line)

        for c in call['subcalls']:
            go(c, lvl + 1)

    go(call, 0)


# Whether to show call traces for detailed math ops.
# Some of this info is redundant rn, but the call traces are not.
SHOW_MATH_TRACES = True


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

    # DEBUG: The following call fails with a KeyError
    print(tracer.trace_tx(tx_total))

    # The two pieces of info are essentially redundant (the tracer events being more fine grained), but show them both to double check.
    tx_total.call_trace()
    print()
    print_call_tree(tracer_events2call_tree(tx_total))

    if SHOW_MATH_TRACES:
        print("\n  -- Math Ops --\n")
        rows = []
        tx = gyro_cemm_math_testing.calculateInvariant.transact(scale(init_amounts_in), params, derived)
        tx.call_trace()  # Uncomment for details
        rows.append(("calculateInvariant", gas_without_call_cost(tx)))

        rows.append(("SUM", sum(row[1] for row in rows)))
        rows.append(("TOTAL TX incl wrapper", gas_without_call_cost(tx_total)))

        print(tabulate(rows))
        print("\n")

    return

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

    tx_total.call_trace()
    print()
    print_call_tree(tracer_events2call_tree(tx_total))

    if SHOW_MATH_TRACES:
        print("\n  -- Math Ops --\n")
        rows = []

        tx = gyro_cemm_math_testing.calculateInvariant.transact(balances, params, derived)
        tx.call_trace()  # Uncomment for details
        rows.append(("calculateInvariant", gas_without_call_cost(tx)))
        invariantBeforeAction = tx.return_value

        tx = gyro_cemm_math_testing._calcAllTokensInGivenExactBptOut.transact(balances, scale(bpt_amount_out), mock_vault_pool.totalSupply())
        tx.call_trace()
        rows.append(("_calcAllTokensInGivenExactBptOut", gas_without_call_cost(tx)))

        tx = gyro_cemm_math_testing.liquidityInvariantUpdate.transact(invariantBeforeAction, scale(bpt_amount_out), mock_vault_pool.totalSupply(), True)
        tx.call_trace()
        rows.append(("liquidityInvariantUpdate", gas_without_call_cost(tx)))

        rows.append(("SUM", sum(row[1] for row in rows)))
        rows.append(("TOTAL TX incl wrapper", gas_without_call_cost(tx_total)))
        print(tabulate(rows))
        print("\n")

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

    tx_total.call_trace()
    print()
    print_call_tree(tracer_events2call_tree(tx_total))

    if SHOW_MATH_TRACES:
        print("\n  -- Math Ops --\n")
        rows = []

        tx = gyro_cemm_math_testing.calculateInvariantWithError.transact(balances, params, derived)
        tx.call_trace()  # Uncomment for details
        rows.append(("calculateInvariantWithError", gas_without_call_cost(tx)))
        invariantBefore, invariantBeforeError = tx.return_value
        invariantBeforeOverUnder = (invariantBefore + 2  * invariantBeforeError, invariantBefore)

        tx = gyro_cemm_math_testing.calcOutGivenIn.transact(balances, scale(amount_to_swap), True, params, derived, invariantBeforeOverUnder)
        tx.call_trace()  # Uncomment for details
        rows.append(("calcOutGivenIn", gas_without_call_cost(tx)))

        rows.append(("SUM", sum(row[1] for row in rows)))
        rows.append(("TOTAL TX incl wrapper", gas_without_call_cost(tx_total)))
        print(tabulate(rows))
        print("\n")

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

    tx_total.call_trace()
    print()
    print_call_tree(tracer_events2call_tree(tx_total))

    if SHOW_MATH_TRACES:
        print("\n  -- Math Ops --\n")
        rows = []

        tx = gyro_cemm_math_testing.calculateInvariantWithError.transact(balances, params, derived)
        tx.call_trace()  # Uncomment for details
        rows.append(("calculateInvariantWithError", gas_without_call_cost(tx)))
        invariantBefore, invariantBeforeError = tx.return_value
        invariantBeforeOverUnder = (invariantBefore + 2 * invariantBeforeError, invariantBefore)

        tx = gyro_cemm_math_testing.calcOutGivenIn.transact(balances, scale(amount_to_swap), True, params, derived,
            invariantBeforeOverUnder)
        tx.call_trace()  # Uncomment for details
        rows.append(("calcOutGivenIn", gas_without_call_cost(tx)))

        rows.append(("SUM", sum(row[1] for row in rows)))
        rows.append(("TOTAL TX incl wrapper", gas_without_call_cost(tx_total)))
        print(tabulate(rows))
        print("\n")

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

    tx_total.call_trace()
    print()
    print_call_tree(tracer_events2call_tree(tx_total))

    if SHOW_MATH_TRACES:
        print("\n  -- Math Ops --\n")
        rows = []

        tx = gyro_cemm_math_testing.calculateInvariant.transact(balances, params, derived)
        tx.call_trace()  # Uncomment for details
        rows.append(("calculateInvariant", gas_without_call_cost(tx)))
        invariantBeforeAction = tx.return_value

        tx = gyro_cemm_math_testing._calcAllTokensInGivenExactBptOut.transact(balances, scale(bpt_amount_out), mock_vault_pool.totalSupply())
        tx.call_trace()
        rows.append(("_calcAllTokensInGivenExactBptOut", gas_without_call_cost(tx)))

        tx = gyro_cemm_math_testing.liquidityInvariantUpdate.transact(invariantBeforeAction, scale(bpt_amount_out), mock_vault_pool.totalSupply(), True)
        tx.call_trace()
        rows.append(("liquidityInvariantUpdate", gas_without_call_cost(tx)))

        rows.append(("SUM", sum(row[1] for row in rows)))
        rows.append(("TOTAL TX incl wrapper", gas_without_call_cost(tx_total)))
        print(tabulate(rows))
        print("\n")

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

    tx_total.call_trace()
    print()
    print_call_tree(tracer_events2call_tree(tx_total))

    if SHOW_MATH_TRACES:
        print("\n  -- Math Ops --\n")
        rows = []

        tx = gyro_cemm_math_testing.calculateInvariantWithError.transact(balances, params, derived)
        tx.call_trace()  # Uncomment for details
        rows.append(("calculateInvariantWithError", gas_without_call_cost(tx)))
        invariantBefore, invariantBeforeError = tx.return_value
        invariantBeforeOverUnder = (invariantBefore + 2 * invariantBeforeError, invariantBefore)

        tx = gyro_cemm_math_testing.calcOutGivenIn.transact(balances, scale(amount_to_swap), True, params, derived,
            invariantBeforeOverUnder)
        tx.call_trace()  # Uncomment for details
        rows.append(("calcOutGivenIn", gas_without_call_cost(tx)))

        rows.append(("SUM", sum(row[1] for row in rows)))
        rows.append(("TOTAL TX incl wrapper", gas_without_call_cost(tx_total)))
        print(tabulate(rows))
        print("\n")

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

    tx_total.call_trace()
    print()
    print_call_tree(tracer_events2call_tree(tx_total))

    if SHOW_MATH_TRACES:
        print("\n  -- Math Ops --\n")
        rows = []

        tx = gyro_cemm_math_testing.calculateInvariant.transact(balances, params, derived)
        tx.call_trace()  # Uncomment for details
        rows.append(("calculateInvariant", gas_without_call_cost(tx)))
        invariantBeforeAction = tx.return_value

        tx = gyro_cemm_math_testing._calcTokensOutGivenExactBptIn.transact(balances, scale(bpt_amount_in), mock_vault_pool.totalSupply())
        tx.call_trace()
        rows.append(("_calcTokensOutGivenExactBptIn", gas_without_call_cost(tx)))

        tx = gyro_cemm_math_testing.liquidityInvariantUpdate.transact(invariantBeforeAction, scale(bpt_amount_in), mock_vault_pool.totalSupply(), False)
        tx.call_trace()
        rows.append(("liquidityInvariantUpdate", gas_without_call_cost(tx)))

        rows.append(("SUM", sum(row[1] for row in rows)))
        rows.append(("TOTAL TX incl wrapper", gas_without_call_cost(tx_total)))
        print(tabulate(rows))
        print("\n")
