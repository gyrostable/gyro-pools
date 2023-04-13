import json
import os
from decimal import Decimal
from os import path

from brownie import Gyro2CLPPool, Gyro3CLPPool, GyroECLPPool, interface, ERC20, GyroECLPPoolFactory, ZERO_ADDRESS, ConstRateProvider  # type: ignore
from brownie import Gyro2CLPPoolFactory, Gyro3CLPPoolFactory  # type: ignore
from brownie import web3
from brownie.network import chain
from tests.conftest import scale_eclp_params
from tests.geclp import eclp_prec_implementation
from tests.support.quantized_decimal import QuantizedDecimal
from tests.support.types import (
    CapParams,
    ECLPFactoryCreateParams,
    ECLPMathParamsQD,
    ThreePoolFactoryCreateParams,
    TwoPoolFactoryCreateParams,
)
from tests.support.utils import scale

from scripts.constants import CONFIG_PATH, DEPLOYED_FACTORIES, PAUSE_MANAGER, POOL_OWNER, TEST_CONST_RATE_PROVIDER_POLYGON
from scripts.mainnet_contracts import get_token_address
from scripts.utils import abort, get_deployer, make_tx_params, with_deployed

from scripts.constants import CONFIG_PATH, DEPLOYED_FACTORIES, PAUSE_MANAGER, POOL_OWNER
from scripts.mainnet_contracts import get_token_address
from scripts.pool_utils import compute_bounds_sqrts
from scripts.utils import (
    JSONEncoder,
    abort,
    get_deployer,
    make_tx_params,
    with_deployed,
)


def set_rate():
    deployer = get_deployer()
    rate_provider = ConstRateProvider.at(TEST_CONST_RATE_PROVIDER_POLYGON)
    params = make_tx_params()
    params['from'] = deployer
    rate_provider.setRate(int(1.5*1e18), params)


def main():
    deployer = get_deployer()
    print(f"deployer = {deployer}")
    contract = deployer.deploy(
        ConstRateProvider,
        **make_tx_params(),
    )
    print(contract.address)
