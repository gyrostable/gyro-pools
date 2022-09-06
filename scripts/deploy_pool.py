import json
import os
from decimal import Decimal
from os import path

from brownie import Gyro2CLPPool, Gyro2CLPPoolFactory, Gyro3CLPPool  # type: ignore
from brownie import Gyro3CLPPoolFactory, GyroCEMMPool, interface  # type: ignore
from brownie import web3
from brownie.network import chain
from tests.support.types import (
    CapParams,
    CEMMPoolParams,
    GyroCEMMMathDerivedParams,
    GyroCEMMMathParams,
    ThreePoolFactoryCreateParams,
    TwoPoolBaseParams,
    TwoPoolFactoryCreateParams,
)
from tests.support.utils import scale

from scripts.constants import CONFIG_PATH, DEPLOYED_FACTORIES, PAUSE_MANAGER, POOL_OWNER
from scripts.mainnet_contracts import get_token_address
from scripts.pool_utils import compute_bounds_sqrts
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


def eclp():
    cemm_pool_factory = interface.IGyroCEMMPoolFactory(
        DEPLOYED_FACTORIES[chain.id]["eclp"]
    )
    deployer = get_deployer()
    cemm_params = GyroCEMMMathParams(
        "1000000000000000",
        "2000000000000000000",
        "707106781186547524",
        "707106781186547524",
        "50000000000000000000",
    )
    # Pre-calculated derived params from above cemm_params values
    derived_params = GyroCEMMMathDerivedParams(
        [
            "-99979925885928775144265228221440915787",
            "2003601717954248326714904773767014148",
        ],
        [
            "99820484546577868536962848308342019089",
            "5989229072794672112217770898500521145",
        ],
        "99900205216253321727351274847867663526",
        "3996415395374460214935365647812318782",
        "1992813677420211890492062487589071518",
        "-79720669675453303560805924511158495",
        "999999999999999998866240933421061152",
    )
    params = (
        "TEST Gyro CEMM Pool",
        "GYRO-CEMM",
        [
            "0x11fb9071e69628d804bf0b197cc61eeacd4aaecf",
            "0x4ea2110a3e277b10c9b098f61d72f58efa8655db",
        ],
        cemm_params,
        derived_params,
        "90000000000000000",
        False,
        "0x4277f6Ea8567EC89A3E81961598fEf33b43A265F",
    )
    tx = cemm_pool_factory.create(
        *params,
        {
            "from": deployer,
            **make_tx_params(),
            "gas_limit": 30000000,
            "allow_revert": True,
        },
    )
    pool_address = tx.events["PoolCreated"]["pool"]
    GyroCEMMPool.at(pool_address)
