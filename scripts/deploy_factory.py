import brownie
from brownie import Gyro3CLPPoolFactory, Gyro2CLPPoolFactory, GyroECLPPoolFactory, GyroECLPMath  # type: ignore
from brownie.network import chain

from scripts.constants import BALANCER_ADDRESSES, GYROSCOPE_ADDRESSES
from scripts.utils import get_deployer, make_tx_params


def _deploy_factory(contract):
    deployer = get_deployer()
    deployer.deploy(
        contract,
        BALANCER_ADDRESSES[chain.id]["vault"],
        GYROSCOPE_ADDRESSES[chain.id]["gyro_config"],
        **make_tx_params(),
        publish_source=True
    )


def c2lp():
    _deploy_factory(Gyro2CLPPoolFactory)


def c3lp():
    _deploy_factory(Gyro3CLPPoolFactory)


def eclp():
    query_processor_attr = (
        "QueryProcessor"
        if hasattr(brownie, "QueryProcessor")
        else "node_modules/@balancer-labs/QueryProcessor"
    )
    QueryProcessor = getattr(brownie, query_processor_attr)

    QueryProcessor.at(BALANCER_ADDRESSES[chain.id]["query_processor"])
    if len(GyroECLPMath) == 0:
        deployer = get_deployer()
        deployer.deploy(GyroECLPMath, **make_tx_params())
    _deploy_factory(GyroECLPPoolFactory)
