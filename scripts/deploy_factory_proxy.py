from brownie import (
    GyroTwoPoolFactory,
    GyroThreePoolFactory,
    FreezableTransparentUpgradeableProxy,
)
from brownie.network import chain
from scripts.constants import GYROSCOPE_ADDRESSES  # type: ignore
from scripts.utils import (
    get_deployer,
    make_tx_params,
    with_deployed,
)


@with_deployed(GyroTwoPoolFactory)
def c2lp(two_pool_factory):
    deployer = get_deployer()
    deployer.deploy(
        FreezableTransparentUpgradeableProxy,
        two_pool_factory,
        GYROSCOPE_ADDRESSES[chain.id]["proxy_admin"],
        b"",
        **make_tx_params(),
    )


@with_deployed(GyroThreePoolFactory)
def c3lp(three_pool_factory):
    deployer = get_deployer()
    deployer.deploy(
        FreezableTransparentUpgradeableProxy,
        three_pool_factory,
        GYROSCOPE_ADDRESSES[chain.id]["proxy_admin"],
        b"",
        **make_tx_params(),
    )
