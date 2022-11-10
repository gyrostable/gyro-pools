from brownie import (
    Gyro2CLPPoolFactory,
    Gyro3CLPPoolFactory,
    FreezableTransparentUpgradeableProxy,
    GyroECLPPoolFactory,
)
from brownie.network import chain
from scripts.constants import GYROSCOPE_ADDRESSES  # type: ignore
from scripts.utils import (
    get_deployer,
    make_tx_params,
    with_deployed,
)


@with_deployed(Gyro2CLPPoolFactory)
def c2lp(two_pool_factory):
    deployer = get_deployer()
    deployer.deploy(
        FreezableTransparentUpgradeableProxy,
        two_pool_factory,
        GYROSCOPE_ADDRESSES[chain.id]["proxy_admin"],
        b"",
        **make_tx_params(),
    )


@with_deployed(Gyro3CLPPoolFactory)
def c3lp(three_pool_factory):
    deployer = get_deployer()
    deployer.deploy(
        FreezableTransparentUpgradeableProxy,
        three_pool_factory,
        GYROSCOPE_ADDRESSES[chain.id]["proxy_admin"],
        b"",
        **make_tx_params(),
    )


@with_deployed(GyroECLPPoolFactory)
def eclp(eclp_pool_factory):
    deployer = get_deployer()
    deployer.deploy(
        FreezableTransparentUpgradeableProxy,
        eclp_pool_factory,
        GYROSCOPE_ADDRESSES[chain.id]["proxy_admin"],
        b"",
        **make_tx_params(),
    )
