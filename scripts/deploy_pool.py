import json
import os
from os import path
from brownie import Gyro2CLPPoolFactory, Gyro3CLPPoolFactory, Gyro2CLPPool, Gyro3CLPPool  # type: ignore
from brownie.network import chain

from scripts.constants import (
    CONFIG_PATH,
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
    return sorted([get_token_address(token) for token in config["tokens"]])


@with_deployed(Gyro2CLPPoolFactory)
def c2lp(two_pool_factory):
    deployer = get_deployer()
    pool_config = _get_config()
    sqrts = [scale(v) for v in pool_config["sqrts"]]
    tx = two_pool_factory.create(
        pool_config["name"],
        pool_config["symbol"],
        _get_tokens(pool_config),
        sqrts,
        scale(pool_config["swap_fee_percentage"]),
        pool_config["oracle_enabled"],
        POOL_OWNER[chain.id],
        {"from": deployer, **make_tx_params()},
    )
    pool_address = tx.events["PoolCreated"]["pool"]
    Gyro2CLPPool.at(pool_address)


@with_deployed(Gyro3CLPPoolFactory)
def c3lp(three_pool_factory):
    deployer = get_deployer()
    pool_config = _get_config()
    tx = three_pool_factory.create(
        pool_config["name"],
        pool_config["symbol"],
        _get_tokens(pool_config),
        scale(pool_config["root_3_alpha"]),
        scale(pool_config["swap_fee_percentage"]),
        POOL_OWNER[chain.id],
        {"from": deployer, **make_tx_params()},
    )
    pool_address = tx.events["PoolCreated"]["pool"]
    Gyro3CLPPool.at(pool_address)
