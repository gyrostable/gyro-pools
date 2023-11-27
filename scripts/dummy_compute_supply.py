
# Like compute_supply but initialize with fixed values. This essentially only resolves contract addreses and handles decimals.

# Usage: brownie run <this> eclp "{'DAI': 10, 'GYD': 10}" --network=mainnet
# NB this doesn't need brownie, we don't do any chain requests. Only use chain.id.
# We also don't do rate-scaling.
# NB overlaps with compute_supply's new fixed-price/amount features but whatever.

from tests.support.utils import scale
from tests.support.quantized_decimal import QuantizedDecimal as D
from scripts.constants import DECIMALS, TOKEN_ADDRESSES
import json

from brownie import *

def eclp(dict_s: str, outfile: str):
    """dict_s: Dict of {asset: amount} in *unscaled* values. Python-compatible syntax, will be eval'd."""
    cfg = eval(dict_s)
    assert isinstance(cfg, dict)

    ret = {}
    for token, uamount in cfg.items():
        token_address = TOKEN_ADDRESSES[chain.id][token]
        decimals = DECIMALS[token]
        amount = int(scale(D(uamount), decimals))
        ret[token_address] = amount

    ret = {'amounts': ret}

    with open(outfile, "w") as f:
        json.dump(ret, f, indent=2)
