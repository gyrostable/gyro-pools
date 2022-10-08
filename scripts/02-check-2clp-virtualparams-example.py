# Check for a weird behavior we saw with some pool states.
# See: https://polygonscan.com/address/0x08b83439aeaccbcfb172a7327af38832fb9b7af4
# This is from config/pools/2clp-wbtc-weth.json

from brownie import *
from brownie.convert import to_address
import json
from scripts.mainnet_contracts import _token_addresses
from tests.support.types import TwoPoolBaseParams, TwoPoolParams, CallJoinPoolGyroParams
from tests.support.utils import scale, to_decimal

token_addresses = _token_addresses[137]  # 137 = polygon chain id

admin = accounts[0]
users = accounts[:3]

authorizer = admin.deploy(Authorizer, admin)
mock_vault = admin.deploy(MockVault, authorizer)
mock_gyro_config = admin.deploy(MockGyroConfig)

# Not used in code, but needs to be deployed.
admin.deploy(QueryProcessor)

BALANCES_SCALED = [to_decimal(100), to_decimal(100)]  # TEST


def main():
    with open("config/pools/2clp-wbtc-weth.json") as f:
        cfg = json.load(f)

    tokens = [to_address(token_addresses[t]) for t in cfg["tokens"]]
    assert tokens[0] < tokens[1]

    # We create dummy addresses instead. But order matters of course!
    tokens = [admin.deploy(SimpleERC20) for i in range(2)]
    tokens.sort(key=lambda t: t.address)
    for t in tokens:
        t.mint(admin, 1000)

    base_params = TwoPoolBaseParams(
        vault=mock_vault.address,
        name="Gyro2CLPPool",  # string
        symbol="GTP",  # string
        token0=tokens[0].address,  # IERC20
        token1=tokens[1].address,  # IERC20
        swapFeePercentage=scale(to_decimal(cfg["swap_fee_percentage"])),
        pauseWindowDuration=0,  # uint256
        bufferPeriodDuration=0,  # uint256
        oracleEnabled=cfg["oracle_enabled"],  # bool
        owner=admin,  # address
    )

    args = TwoPoolParams(
        baseParams=base_params,
        sqrtAlpha=scale(to_decimal(cfg["sqrts"][0])),
        sqrtBeta=scale(to_decimal(cfg["sqrts"][1])),
    )

    pool = admin.deploy(Gyro2CLPPool, args, mock_gyro_config.address)

    poolId = pool.getPoolId()
    init_amounts_in = BALANCES_SCALED

    # Initialize
    mock_vault.callJoinPoolGyro(
        CallJoinPoolGyroParams(
            pool.address,
            poolId,
            users[0],
            users[0],
            (0, 0),  # current balances
            0,
            scale(to_decimal(cfg["swap_fee_percentage"])),
            scale(init_amounts_in),
            0,  # amount_out not used for init
        )
    )

    print(pool.getVirtualParameters())
