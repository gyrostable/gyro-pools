# Similar to `compute_supply.py` but without pulling price data. Instead, both amounts are specified.

# Usage:
# Set environment variables AMOUNT_RS_XXX for *all* tokens
# $ brownie run --network=polygon-main $0 main <configfile.json> [outputfile.json]

import json
import os
import pprint

from brownie import chain

from .compute_supply import get_rates
from scripts.constants import DECIMALS, TOKEN_ADDRESSES
from tests.support.quantized_decimal import QuantizedDecimal


POOL_TYPE_TO_N_TOKENS = {
    "eclp": 2,
    "2clp": 2,
    "3clp": 3,
}


def get_env_amounts_rs(tokens):
    return [QuantizedDecimal(os.environ[f"AMOUNT_RS_{t}"]) for t in tokens]


def main(config: str, output: str = None):
    chain_id = chain.id
    with open(config) as f:
        pool_config = json.load(f)

    pool_type = pool_config["pool_type"]
    n_tokens = POOL_TYPE_TO_N_TOKENS[pool_type]

    tokens = pool_config["tokens"]
    assert len(tokens) == n_tokens, f"{pool_type} should have {n_tokens} tokens"
    token_addresses = [TOKEN_ADDRESSES[chain_id][t] for t in tokens]
    decimals = [DECIMALS[t] for t in tokens]

    rate_providers_dict = pool_config.get("rate_providers", dict())
    rate_provider_addresses = [rate_providers_dict.get(k) for k in tokens]
    rates = get_rates(rate_provider_addresses)

    amounts_rs = get_env_amounts_rs(tokens)
    amounts = [x_rs / rate for x_rs, rate in zip(amounts_rs, rates)]

    result = {
        "amounts": {
            addr: int(x * 10**d)
            for addr, x, d in zip(token_addresses, amounts, decimals)
        },
        "unscaled_amounts": {
            addr: float(x) for addr, x in zip(token_addresses, amounts)
        },
    }

    if output:
        pprint.pprint(result)
        with open(output, "w") as f:
            json.dump(result, f, indent=2)
    else:
        print(json.dumps(result, indent=2))
