import json
import os
from os import path
from brownie import Gyro2CLPPoolFactory, Gyro3CLPPoolFactory, Gyro2CLPPool, Gyro3CLPPool, interface, FreezableTransparentUpgradeableProxy  # type: ignore
from brownie.network import chain
from tests.support.types import CapParams, TwoPoolFactoryCreateParams

from scripts.constants import (
    CONFIG_PATH,
    PAUSE_MANAGER,
    POOL_OWNER,
)
from scripts.mainnet_contracts import get_token_address
from scripts.utils import abort, get_deployer, make_tx_params, with_deployed
from tests.support.utils import scale


def _get_config():
    pool_name = os.environ.get("POOL_NAME")
    if not pool_name:
        abort("POOL_NAME environment variable must be set")
    with open(path.join(CONFIG_PATH, "pools", pool_name + ".json")) as f:
        return json.load(f)


def _get_tokens(config, is_fork):
    return sorted([get_token_address(token, is_fork) for token in config["tokens"]])


@with_deployed(Gyro2CLPPoolFactory)
def c2lp(two_pool_factory):
    two_pool_factory = interface.IGyro2CLPPoolFactory(
        FreezableTransparentUpgradeableProxy[0].address
    )
    deployer = get_deployer()
    pool_config = _get_config()
    sqrts = [round(scale(v).raw) for v in pool_config["sqrts"]]
    params = TwoPoolFactoryCreateParams(
        name=pool_config["name"],
        symbol=pool_config["symbol"],
        tokens=_get_tokens(pool_config, is_fork=False),
        sqrts=sqrts,
        swapFeePercentage=round(scale(pool_config["swap_fee_percentage"]).raw),
        oracleEnabled=pool_config["oracle_enabled"],
        owner=POOL_OWNER[chain.id],
        cap_manager=POOL_OWNER[chain.id],
        cap_params=CapParams(
            cap_enabled=pool_config["cap"]["enabled"],
            global_cap=round(scale(pool_config["cap"]["global"]).raw),
            per_address_cap=round(scale(pool_config["cap"]["per_address"]).raw),
        ),
        pause_manager=PAUSE_MANAGER[chain.id],
    )
    tx = two_pool_factory.create(
        *params,
        {"from": deployer, **make_tx_params()},
    )
    pool_address = tx.events["PoolCreated"]["pool"]
    Gyro2CLPPool.at(pool_address)


@with_deployed(Gyro3CLPPoolFactory)
def c3lp(three_pool_factory):
    three_pool_factory = interface.IGyro3CLPPoolFactory(
        FreezableTransparentUpgradeableProxy[1].address
    )
    deployer = get_deployer()
    pool_config = _get_config()
    tx = three_pool_factory.create(
        pool_config["name"],
        pool_config["symbol"],
        _get_tokens(pool_config, is_fork=False),
        scale(pool_config["root_3_alpha"]),
        scale(pool_config["swap_fee_percentage"]),
        POOL_OWNER[chain.id],
        {"from": deployer, **make_tx_params()},
    )
    pool_address = tx.events["PoolCreated"]["pool"]
    Gyro3CLPPool.at(pool_address)
