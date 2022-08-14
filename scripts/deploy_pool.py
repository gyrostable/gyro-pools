import json
import os
from os import path
from brownie import Gyro2CLPPool, Gyro3CLPPool, interface  # type: ignore
from brownie.network import chain
from tests.support.types import (
    CapParams,
    ThreePoolFactoryCreateParams,
    TwoPoolFactoryCreateParams,
)

from scripts.constants import (
    CONFIG_PATH,
    DEPLOYED_FACTORIES,
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


def _get_tokens(config):
    return sorted([get_token_address(token, False) for token in config["tokens"]])


def c2lp():
    two_pool_factory = interface.IGyro2CLPPoolFactory(
        DEPLOYED_FACTORIES[chain.id]["c2lp"]
    )
    deployer = get_deployer()
    pool_config = _get_config()
    sqrts = [round(scale(v).raw) for v in pool_config["sqrts"]]
    params = TwoPoolFactoryCreateParams(
        name=pool_config["name"],
        symbol=pool_config["symbol"],
        tokens=_get_tokens(pool_config),
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


def c3lp():
    three_pool_factory = interface.IGyro3CLPPoolFactory(
        DEPLOYED_FACTORIES[chain.id]["c3lp"]
    )
    deployer = get_deployer()
    pool_config = _get_config()
    params = (
        ThreePoolFactoryCreateParams(
            name=pool_config["name"],
            symbol=pool_config["symbol"],
            tokens=_get_tokens(pool_config),
            root3Alpha=scale(pool_config["root_3_alpha"]),
            swapFeePercentage=scale(pool_config["swap_fee_percentage"]),
            owner=POOL_OWNER[chain.id],
            cap_manager=POOL_OWNER[chain.id],
            cap_params=CapParams(
                cap_enabled=pool_config["cap"]["enabled"],
                global_cap=round(scale(pool_config["cap"]["global"]).raw),
                per_address_cap=round(scale(pool_config["cap"]["per_address"]).raw),
            ),
            pause_manager=PAUSE_MANAGER[chain.id],
        ),
    )
    tx = three_pool_factory.create(
        *params,
        {"from": deployer, **make_tx_params()},
    )
    pool_address = tx.events["PoolCreated"]["pool"]
    Gyro3CLPPool.at(pool_address)
