import argparse
import json
import sys
from decimal import Decimal
from os import path

sys.path.insert(0, path.dirname(path.dirname(__file__)))

from tests.support.quantized_decimal import QuantizedDecimal
from tests.support.types import ECLPMathParamsQD, convd, params2MathParams, paramsTo100
from tests.geclp import eclp_prec_implementation

from tests.geclp import eclp_100 as mimpl
from tests.support.quantized_decimal_100 import QuantizedDecimal as D3

from scripts.coingecko import get_prices
from scripts.rate_providers import get_rates
from scripts.constants import DECIMALS, TOKEN_ADDRESSES
from scripts.pool_utils import compute_bounds_sqrts

from brownie import chain

# Run via:
# $ brownie run --network=polygon-main $0 main <configfile.json> [outputfile.json]


TWO_CLP_L_INIT = Decimal("1e-2")  # can set to w/e, choose so that x,y are small
THREE_CLP_L_INIT = 100  # can set to w/e, choose so that x,y,z are small
E_CLP_L_INIT = Decimal("2e-3")  # can set to w/e, choose so that x,y,z are small
# SOMEDAY ^ The value of these depends on the parameters actually. A more stable variant would be to
# initialize from portfolio value instead.


def compute_amounts_2clp(pool_config: dict, chain_id: int):
    assert len(pool_config["tokens"]) == 2, "2CLP should have 2 tokens"

    token_addresses = [TOKEN_ADDRESSES[chain_id][t] for t in pool_config["tokens"]]
    dx, dy = [DECIMALS[t] for t in pool_config["tokens"]]
    sqrt_alpha, sqrt_beta = compute_bounds_sqrts(token_addresses, pool_config["bounds"])
    assert token_addresses[0] <= token_addresses[1]

    prices = get_prices(token_addresses, chain_id)
    px, py = [Decimal.from_float(prices[a]) for a in token_addresses]
    pr = px / py

    assert pr >= sqrt_alpha**2
    assert pr <= sqrt_beta**2

    L_init = TWO_CLP_L_INIT

    x = L_init * (1 / pr.sqrt() - 1 / sqrt_beta)
    y = L_init * (pr.sqrt() - sqrt_alpha)
    S_init = x * pr + y
    p_bpt = (x * px + y * py) / S_init
    # ^ p_bpt = py up to rounding errors by design

    return {
        "amounts": {
            token_addresses[0]: round(x * 10**dx),
            token_addresses[1]: round(y * 10**dy),
        },
        "sqrts": [str(sqrt_alpha), str(sqrt_beta)],
        "prices": {
            token_addresses[0]: float(px),
            token_addresses[1]: float(py),
        },
        "initial_supply": float(S_init),
        "price_bpt": float(p_bpt),
    }


def compute_amounts_3clp(pool_config: dict, chain_id: int):
    assert len(pool_config["tokens"]) == 3, "ECLP should have 3 tokens"

    tokens = [
        (TOKEN_ADDRESSES[chain_id][t], DECIMALS[t]) for t in pool_config["tokens"]
    ]
    tokens_sorted = sorted(
        tokens,
        key=lambda x: x[0].lower(),
    )
    assert tokens == tokens_sorted

    prices_dict = get_prices([t for t, _ in tokens], chain_id)
    prices = [Decimal.from_float(prices_dict[t]) for t, _ in tokens]
    px, py, pz = prices
    pxz, pyz = px / pz, py / pz

    cbrt_alpha = Decimal(pool_config["root_3_alpha"])

    assert pxz * pyz >= cbrt_alpha**3
    assert pxz / pyz**2 >= cbrt_alpha**3
    assert pyz / pxz**2 >= cbrt_alpha**3

    L_init = THREE_CLP_L_INIT

    cbrtpxpy = (pxz * pyz) ** (Decimal("1") / 3)
    x = L_init * (cbrtpxpy / pxz - cbrt_alpha)
    y = L_init * (cbrtpxpy / pyz - cbrt_alpha)
    z = L_init * (cbrtpxpy - cbrt_alpha)
    amounts = [x, y, z]
    S_init = x * pxz + y * pyz + z
    p_bpt = (x * px + y * py + z * pz) / S_init
    # ^ p_bpt = pz up to rounding errors by design.

    return {
        "amounts": {t: round(v * 10**d) for (t, d), v in zip(tokens, amounts)},
        "cbrt_alpha ": str(cbrt_alpha),
        "prices": {t: str(p) for (t, _), p in zip(tokens, prices)},
        "initial_supply": float(S_init),
        "price_bpt": float(p_bpt),
    }


def compute_amounts_eclp(pool_config: dict, chain_id: int):
    assert len(pool_config["tokens"]) == 2, "ECLP should have 2 tokens"

    token_addresses = [TOKEN_ADDRESSES[chain_id][t] for t in pool_config["tokens"]]
    dx, dy = [DECIMALS[t] for t in pool_config["tokens"]]
    prices = get_prices(token_addresses, chain_id)
    px, py = [Decimal.from_float(prices[a]) for a in token_addresses]
    # Rate scaling
    rate_providers_dict = pool_config.get("rate_providers", dict())
    rate_provider_addresses = [
        rate_providers_dict.get(k) for k in pool_config["tokens"]
    ]
    rx, ry = get_rates(rate_provider_addresses)

    if token_addresses[0] > token_addresses[1]:
        token_addresses = token_addresses[::-1]
        dx, dy = dy, dx
        px, py = py, px
        rx, ry = ry, rx

    # rate-scaled relative price
    pr_s = ry / rx * px / py

    params = ECLPMathParamsQD(
        **{k: QuantizedDecimal(v) for k, v in pool_config["params"].items()}
    )
    # derived_params = eclp_prec_implementation.calc_derived_values(params)

    assert pr_s >= params.alpha
    assert pr_s <= params.beta

    # We run ECLP math calculations using the "old" (unoptimized) implementation but in 100
    # decimals b/c we don't have an optimized implementation for this.
    pr_100 = convd(pr_s, D3)
    r_100 = convd(E_CLP_L_INIT, D3)
    mparams_100 = params2MathParams(paramsTo100(params))
    eclp = mimpl.ECLP.from_px_r(pr_100, r_100, mparams_100)
    x_s, y_s = convd(eclp.x, QuantizedDecimal), convd(eclp.y, QuantizedDecimal)

    # Go from rate-scaled to non-rate-scaled amounts
    x = x_s / rx
    y = y_s / ry

    S_init = x_s * pr_s + y_s
    p_bpt = (x * px + y * py) / S_init
    # ^ p_bpt = py / ry up to rounding errors by design.

    return {
        "amounts": {
            token_addresses[0]: int(x * 10**dx),
            token_addresses[1]: int(y * 10**dy),
        },
        "unscaled_amounts": {
            token_addresses[0]: float(x),
            token_addresses[1]: float(y),
        },
        "scaled_relative_price": float(pr_s),
        "params": pool_config["params"],
        "prices": {
            token_addresses[0]: float(px),
            token_addresses[1]: float(py),
        },
        "initial_supply": float(S_init),
        "price_bpt": float(p_bpt),
    }


def main(config: str, output: str = None):
    chain_id = chain.id
    with open(config) as f:
        pool_config = json.load(f)
        pool_type = pool_config["pool_type"]
        if pool_type == "eclp":
            result = compute_amounts_eclp(pool_config, chain_id)
        elif pool_type == "2clp":
            result = compute_amounts_2clp(pool_config, chain_id)
        elif pool_type == "3clp":
            result = compute_amounts_3clp(pool_config, chain_id)
        else:
            raise ValueError(f"invalid pool type {pool_type}")
    if output:
        with open(output, "w") as f:
            json.dump(result, f, indent=2)
    else:
        print(json.dumps(result, indent=2))
