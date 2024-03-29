import json
import os
from os import path
from typing import List


from brownie import Gyro2CLPPool, Gyro3CLPPool, GyroECLPPool, interface, GyroECLPPoolFactory, ZERO_ADDRESS  # type: ignore
from brownie import Gyro2CLPPoolFactory, Gyro3CLPPoolFactory, PoolOwner  # type: ignore
from brownie import web3
from brownie.network import chain
from tests.geclp import eclp_prec_implementation
from tests.support.quantized_decimal import QuantizedDecimal
from tests.support.types import (
    CapParams,
    ECLPFactoryCreateParams,
    ECLPMathParamsQD,
    ThreePoolFactoryCreateParams,
    TwoPoolFactoryCreateParams,
    PauseParams,
)
from tests.support.utils import scale

from scripts.constants import CONFIG_PATH, DEPLOYED_FACTORIES, PAUSE_MANAGER, POOL_OWNER
from scripts.mainnet_contracts import get_token_address
from scripts.utils import abort, get_deployer, make_tx_params, with_deployed

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


def get_tokens(config, sort=False):
    """
    WARNING: if sort=True, we sort the tokens. However, this can change the meaning of the parameters
    for some pools. For example, 2-CLP price bounds refer to the relative token0/token1 price and for
    the E-CLP, all parameters but lambda are related to this relative price. The same applies to token
    rates.
    It's much safer to have the tokens already sorted in the config.
    """
    tokens = [get_token_address(token, False) for token in config["tokens"]]
    if sort:
        tokens.sort(key=lambda v: v.lower())
    return tokens


def get_rate_providers(tokens: List[str], config: dict) -> List[str]:
    """Optional field, default 0x0."""
    config_rate_providers = config.get("rate_providers", {})
    rate_providers = [
        config_rate_providers.get(t, ZERO_ADDRESS) for t in config["tokens"]
    ]
    if tokens[0].lower() > tokens[1].lower():
        rate_providers = rate_providers[::-1]
    return rate_providers


def get_cap_params(pool_config: dict) -> CapParams:
    raw_params = pool_config.get("cap", {})
    return CapParams(
        cap_enabled=raw_params.get("enabled", False),
        global_cap=int(scale(raw_params.get("global", 0))),
        per_address_cap=int(scale(raw_params.get("per_address", 0))),
    )


def c2lp():
    two_pool_factory = interface.IGyro2CLPPoolFactory(
        DEPLOYED_FACTORIES[chain.id]["c2lp"]
    )
    deployer = get_deployer()
    pool_config = _get_config()
    tokens = get_tokens(pool_config, sort=False)
    rate_providers = get_rate_providers(tokens, pool_config)
    # NB compute_bounds_sqrts() also sorts transforms the sqrts wrt token sort order.
    sqrts = compute_bounds_sqrts(tokens, pool_config["bounds"])
    tokens.sort(key=lambda v: v.lower())
    params = TwoPoolFactoryCreateParams(
        name=pool_config["name"],
        symbol=pool_config["symbol"],
        tokens=tokens,
        sqrts=[round(scale(v).raw) for v in sqrts],
        rate_providers=rate_providers,
        swapFeePercentage=scale(pool_config["swap_fee_percentage"]),
        owner=PoolOwner[0],
        cap_manager=POOL_OWNER[chain.id],
        cap_params=get_cap_params(pool_config),
        pause_manager=PAUSE_MANAGER[chain.id],
        pause_params=PauseParams(
            pause_window_duration=int(
                pool_config["pause"]["window_duration_days"] * 24 * 60 * 60
            ),
            buffer_period_duration=int(
                pool_config["pause"]["buffer_duration_days"] * 24 * 60 * 60
            ),
        ),
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
        owner=PoolOwner[0],
        cap_manager=POOL_OWNER[chain.id],
        cap_params=CapParams(
            cap_enabled=pool_config["cap"]["enabled"],
            global_cap=int(scale(pool_config["cap"]["global"])),
            per_address_cap=int(scale(pool_config["cap"]["per_address"])),
        ),
        pause_manager=PAUSE_MANAGER[chain.id],
        pause_params=PauseParams(
            pause_window_duration=int(
                pool_config["pause"]["window_duration_days"] * 24 * 60 * 60
            ),
            buffer_period_duration=int(
                pool_config["pause"]["buffer_duration_days"] * 24 * 60 * 60
            ),
        ),
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
    if chain.id == 1337:
        eclp_pool_factory = GyroECLPPoolFactory[-1]
    else:
        eclp_pool_factory = interface.IGyroECLPPoolFactory(
            DEPLOYED_FACTORIES[chain.id]["eclp"]
        )
    deployer = get_deployer()
    pool_config = _get_config()
    tokens = get_tokens(pool_config, sort=False)
    rate_providers = get_rate_providers(tokens, pool_config)
    raw_params = {k: QuantizedDecimal(v) for k, v in pool_config["params"].items()}
    if tokens[0] > tokens[1]:
        raw_params["alpha"], raw_params["beta"] = (
            1 / raw_params["beta"],
            1 / raw_params["alpha"],
        )
        raw_params["c"], raw_params["s"] = raw_params["s"], raw_params["c"]
    tokens.sort(key=lambda v: v.lower())
    eclp_params = ECLPMathParamsQD(**raw_params)
    derived_params = eclp_prec_implementation.calc_derived_values(eclp_params)

    params = ECLPFactoryCreateParams(
        name=pool_config["name"],
        symbol=pool_config["symbol"],
        tokens=tokens,
        params=eclp_params.scale(),
        derived_params=derived_params.scale(),
        rate_providers=rate_providers,
        swap_fee_percentage=scale(pool_config["swap_fee_percentage"]),
        owner=PoolOwner[0],
        cap_manager=POOL_OWNER[chain.id],
        cap_params=get_cap_params(pool_config),
        pause_manager=PAUSE_MANAGER[chain.id],
        pause_params=PauseParams(
            pause_window_duration=int(
                pool_config["pause"]["window_duration_days"] * 24 * 60 * 60
            ),
            buffer_period_duration=int(
                pool_config["pause"]["buffer_duration_days"] * 24 * 60 * 60
            ),
        ),
    )
    print(params)
    tx = eclp_pool_factory.create(
        *params,
        {"from": deployer, **make_tx_params()},
    )
    if "PoolCreated" in tx.events:
        pool_address = tx.events["PoolCreated"]["pool"]
    else:
        # TODO the following crashes. (non-critical, the script still works)
        pool_created = (
            GyroECLPPoolFactory[0].events.PoolCreated().processLog(tx.logs[-1])
        )
        pool_address = pool_created["args"]["pool"]
    GyroECLPPool.at(pool_address)
