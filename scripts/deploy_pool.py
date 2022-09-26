from decimal import Decimal
import json
import os
from os import path

from brownie import Gyro2CLPPool, Gyro3CLPPool, interface, Gyro3CLPPoolFactory, web3, Gyro2CLPPoolFactory  # type: ignore
from brownie.network import chain
from scripts.pool_utils import compute_bounds_sqrts
from tests.support.types import (
    CapParams,
    ThreePoolFactoryCreateParams,
    TwoPoolFactoryCreateParams,
)
from tests.support.utils import scale

from scripts.constants import CONFIG_PATH, DEPLOYED_FACTORIES, PAUSE_MANAGER, POOL_OWNER
from scripts.mainnet_contracts import get_token_address
from scripts.utils import (
    JSONEncoder,
    abort,
    get_deployer,
    make_tx_params,
    with_deployed,
)


def _get_config():
    pool_name = os.environ.get("POOL_NAME")
    if not pool_name:
        abort("POOL_NAME environment variable must be set")
    with open(path.join(CONFIG_PATH, "pools", pool_name + ".json")) as f:
        return json.load(f)


def get_tokens(config, sort=True):
    tokens = [get_token_address(token, False) for token in config["tokens"]]
    if sort:
        tokens.sort(key=lambda v: v.lower())
    return tokens


def c2lp():
    two_pool_factory = interface.IGyro2CLPPoolFactory(
        DEPLOYED_FACTORIES[chain.id]["c2lp"]
    )
    deployer = get_deployer()
    pool_config = _get_config()
    tokens = get_tokens(pool_config, sort=False)
    sqrts = compute_bounds_sqrts(tokens, pool_config["bounds"])
    tokens.sort(key=lambda v: v.lower())
    params = TwoPoolFactoryCreateParams(
        name=pool_config["name"],
        symbol=pool_config["symbol"],
        tokens=tokens,
        sqrts=[round(scale(v).raw) for v in sqrts],
        swapFeePercentage=scale(pool_config["swap_fee_percentage"]),
        oracleEnabled=pool_config["oracle_enabled"],
        owner=POOL_OWNER[chain.id],
        cap_manager=POOL_OWNER[chain.id],
        cap_params=CapParams(
            cap_enabled=pool_config["cap"]["enabled"],
            global_cap=int(scale(pool_config["cap"]["global"])),
            per_address_cap=int(scale(pool_config["cap"]["per_address"])),
        ),
        pause_manager=PAUSE_MANAGER[chain.id],
    )
    tx = two_pool_factory.create(
        *params,
        {"from": deployer, **make_tx_params()},
    )
    receipt = web3.eth.getTransactionReceipt(tx.txid)
    evt = Gyro2CLPPoolFactory[0].events.PoolCreated()
    pool_address = evt.processReceipt(receipt)[0]["args"]["pool"]
    Gyro2CLPPool.at(pool_address)
    print(f"Pool deployed at {pool_address}")


def persist_3clp_seed_data(pool_address, tokens):
    filepath = path.join(path.dirname(__file__), "../misc/3clp-seed-data-testing.json")
    amounts = {}
    first_18 = True
    for token in tokens:
        if interface.ERC20(token).decimals() == 6:
            amounts[token] = 36664
        elif first_18:
            amounts[token] = 76675558717198560
            first_18 = False
        else:
            amounts[token] = 36664888493720408
    seeding_data = {"pool": pool_address, "amounts": amounts}
    with open(filepath, "w") as f:
        json.dump(seeding_data, f, indent=4)


def c3lp():
    if chain.id == 1337:
        three_pool_factory = Gyro3CLPPoolFactory[-1]
    else:
        three_pool_factory = interface.IGyro3CLPPoolFactory(
            DEPLOYED_FACTORIES[chain.id]["c3lp"]
        )
    deployer = get_deployer()
    pool_config = _get_config()
    tokens = get_tokens(pool_config)
    params = ThreePoolFactoryCreateParams(
        name=pool_config["name"],
        symbol=pool_config["symbol"],
        tokens=tokens,
        root3Alpha=scale(pool_config["root_3_alpha"]),
        swapFeePercentage=scale(pool_config["swap_fee_percentage"]),
        owner=POOL_OWNER[chain.id],
        cap_manager=POOL_OWNER[chain.id],
        cap_params=CapParams(
            cap_enabled=pool_config["cap"]["enabled"],
            global_cap=int(scale(pool_config["cap"]["global"])),
            per_address_cap=int(scale(pool_config["cap"]["per_address"])),
        ),
        pause_manager=PAUSE_MANAGER[chain.id],
    )
    tx = three_pool_factory.create(params, {"from": deployer, **make_tx_params()})
    receipt = web3.eth.getTransactionReceipt(tx.txid)
    evt = Gyro3CLPPoolFactory[0].events.PoolCreated()
    pool_address = evt.processReceipt(receipt)[0]["args"]["pool"]
    Gyro3CLPPool.at(pool_address)
    print(f"Pool deployed at {pool_address}")

    if chain.id == 1337:
        persist_3clp_seed_data(pool_address, tokens)
