from brownie import PoolOwner, chain  # type: ignore
from scripts.constants import POOL_OWNER
from scripts.utils import get_deployer, make_tx_params


def main():
    deployer = get_deployer()
    pool_owner = deployer.deploy(PoolOwner, **make_tx_params())
    pool_owner.transferOwnership(
        POOL_OWNER[chain.id], {"from": deployer, **make_tx_params()}
    )
