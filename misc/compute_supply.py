import argparse
import json
import sys
from decimal import Decimal
from os import path


sys.path.append(path.dirname(path.dirname(__file__)))


from scripts.coingecko import get_prices
from scripts.constants import DECIMALS, TOKEN_ADDRESSES
from scripts.pool_utils import compute_bounds_sqrts


TWO_CLP_L_INIT = Decimal("1e-2")  # can set to w/e, choose so that x,y are small
THREE_CLP_L_INIT = 100  # can set to w/e, choose so that x,y,z are small

parser = argparse.ArgumentParser(prog="compute-initial-supply")
parser.add_argument("config")
parser.add_argument("-c", "--chain-id", type=int, default=137)
parser.add_argument("-o", "--output", required=True)


def compute_amounts_2clp(pool_config: dict, chain_id: int):
    token_addresses = [TOKEN_ADDRESSES[chain_id][t] for t in pool_config["tokens"]]
    dx, dy = [DECIMALS[t] for t in pool_config["tokens"]]
    sqrt_alpha, sqrt_beta = compute_bounds_sqrts(token_addresses, pool_config["bounds"])
    if token_addresses[0] >= token_addresses[1]:
        token_addresses = token_addresses[::-1]
        dx, dy = dy, dx

    prices = get_prices(token_addresses, chain_id)
    px, py = [Decimal.from_float(prices[a]) for a in token_addresses]

    L_init = TWO_CLP_L_INIT

    pr = px / py
    x = L_init * (1 / pr.sqrt() - 1 / sqrt_beta)
    y = L_init * (pr.sqrt() - sqrt_alpha)
    S_init = L_init * 2
    p_bpt = (x * px + y * py) / S_init

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
    tokens = sorted(
        [(TOKEN_ADDRESSES[chain_id][t], DECIMALS[t]) for t in pool_config["tokens"]],
        key=lambda x: x[0].lower(),
    )
    prices_dict = get_prices([t for t, _ in tokens], chain_id)
    prices = [Decimal.from_float(prices_dict[t]) for t, _ in tokens]

    px = prices[1] / prices[0]
    py = prices[2] / prices[0]
    cbrt_alpha = Decimal(pool_config["root_3_alpha"])

    assert px * py >= cbrt_alpha**3
    assert px / py**2 >= cbrt_alpha**3
    assert py / px**2 >= cbrt_alpha**3

    L_init = THREE_CLP_L_INIT

    cbrtpxpy = (px * py) ** (Decimal("1") / 3)
    x = L_init * (cbrtpxpy / px - cbrt_alpha)
    y = L_init * (cbrtpxpy / py - cbrt_alpha)
    z = L_init * (cbrtpxpy - cbrt_alpha)
    amounts = [x, y, z]
    S_init = L_init * 3
    p_bpt = (px * x + y + z) / S_init

    return {
        "amounts": {t: round(v * 10**d) for (t, d), v in zip(tokens, amounts)},
        "cbrt_alpha ": str(cbrt_alpha),
        "prices": {t: str(p) for (t, _), p in zip(tokens, prices)},
        "initial_supply": float(S_init),
        "price_bpt": float(p_bpt),
    }


def main():
    args = parser.parse_args()
    with open(args.config) as f:
        pool_config = json.load(f)
        if len(pool_config["tokens"]) == 2:
            result = compute_amounts_2clp(pool_config, args.chain_id)
        elif len(pool_config["tokens"]) == 3:
            result = compute_amounts_3clp(pool_config, args.chain_id)
        else:
            raise ValueError("Pool must have 2 or 3 tokens")
    with open(args.output, "w") as f:
        json.dump(result, f, indent=2)


if __name__ == "__main__":
    main()
