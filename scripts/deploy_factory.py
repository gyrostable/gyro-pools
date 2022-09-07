from brownie import Gyro3CLPPoolFactory, Gyro2CLPPoolFactory, GyroCEMMPoolFactory, GyroCEMMMath  # type: ignore
from brownie.network import chain

from scripts.constants import BALANCER_ADDRESSES, GYROSCOPE_ADDRESSES
from scripts.utils import get_deployer, make_tx_params


def _deploy_factory(contract):
    deployer = get_deployer()
    deployer.deploy(
        contract,
        BALANCER_ADDRESSES[chain.id]["vault"],
        GYROSCOPE_ADDRESSES[chain.id]["gyro_config"],
        **make_tx_params()
    )


def c2lp():
    from brownie import QueryProcessor  # type: ignore

    QueryProcessor.at(BALANCER_ADDRESSES[chain.id]["query_processor"])
    _deploy_factory(Gyro2CLPPoolFactory)


def c3lp():
    _deploy_factory(Gyro3CLPPoolFactory)


def eclp():
    from brownie import QueryProcessor  # type: ignore

    QueryProcessor.at(BALANCER_ADDRESSES[chain.id]["query_processor"])
    if len(GyroCEMMMath) == 0:
        deployer = get_deployer()
        deployer.deploy(GyroCEMMMath, **make_tx_params())
    _deploy_factory(GyroCEMMPoolFactory)
