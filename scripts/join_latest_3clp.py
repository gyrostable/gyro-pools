from brownie import Vault, accounts, Gyro3CLPPool, interface
from eth_abi import encode_abi
from tests.support.utils import scale


def main():
    pool = Gyro3CLPPool[-1]
    vault = Vault[0]
    token_infos = vault.getPoolTokens(pool.getPoolId())
    tokens = token_infos[0]
    deployer = accounts[0]
    max_amounts_in = [v * 10_000 for v in token_infos[1]]
    encoded_data = encode_abi(["uint256", "uint256"], [3, 50_000 * 10**18])

    for token, amount in zip(tokens, max_amounts_in):
        tok = interface.ERC20(token)
        allowance = tok.allowance(deployer, vault)
        if allowance < amount:
            tok.approve(vault, amount, {"from": deployer})

    tx = vault.joinPool(
        pool.getPoolId(),
        deployer,
        deployer,
        (tokens, max_amounts_in, encoded_data, False),
        {
            "from": deployer,
            "gas": 5_000_000,
            "allow_revert": True,
            "gas_price": "60 gwei",
        },
    )
