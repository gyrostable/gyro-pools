from brownie import chain, web3, accounts
from brownie import QueryProcessor, ERC20, Authorizer, Vault  # type: ignore
from scripts.constants import GYROSCOPE_ADDRESSES

DEPLOYER_ADDRESS = "0x90F8bf6A479f320ead074411a4B0e7944Ea8c9C1"


def main():
    if chain.id != 1337:
        raise Exception("This script is only for local testing")

    deployer = accounts[0]
    if deployer.address != DEPLOYER_ADDRESS:
        raise Exception(
            "Deployer address mismatch, ganache-cli must be started with `-d` flag"
        )

    gyro_config_address = GYROSCOPE_ADDRESSES[1337]["gyro_config"]
    if len(web3.eth.get_code(gyro_config_address)) == 0:
        raise Exception("Gyro config not deployed as first action from deployer")

    if web3.eth.get_transaction_count(accounts[0].address) != 2:
        raise Exception(
            "Nonce mismatch, only the gyro_config deploy script must be run before this"
        )

    deployer.deploy(QueryProcessor)
    weth = deployer.deploy(ERC20, "Wrapped Ether", "WETH")
    authorizer = deployer.deploy(Authorizer, deployer.address)
    deployer.deploy(Vault, authorizer, weth, 86_400 * 90, 86_400 * 30)
