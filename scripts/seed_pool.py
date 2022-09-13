import json
import os

from brownie import Vault, interface  # type: ignore
from eth_abi import encode_abi

from scripts.utils import get_deployer

SEED_DATA_PATH = os.environ.get("SEED_DATA_PATH")


def main():
    assert SEED_DATA_PATH, "SEED_DATA_PATH environment variable must be set"
    assert os.path.exists(SEED_DATA_PATH), "Config path does not exist"

    deployer = get_deployer()

    with open(SEED_DATA_PATH) as f:
        seed_data = json.load(f)

    vault = Vault[0]

    pool = interface.IBalancerPool(seed_data["pool"])

    pool_id = pool.getPoolId()
    pool_tokens = vault.getPoolTokens(pool_id)[0]

    assert set(seed_data["amounts"]) == set(pool_tokens), "Invalid pool tokens"

    for token, amount in seed_data["amounts"].items():
        erc_token = interface.IERC20(token)
        allowance = erc_token.allowance(deployer, vault)
        if allowance < amount:
            erc_token.approve(vault, amount, {"from": deployer})

    max_amounts_in = [seed_data["amounts"][token] for token in pool_tokens]

    encoded_data = encode_abi(["uint256", "uint256[]"], [0, max_amounts_in])
    user_data = (pool_tokens, max_amounts_in, encoded_data, False)

    args = {"from": deployer, "gas_price": "60 gwei"}

    vault.joinPool(pool_id, deployer, deployer, user_data, args)
