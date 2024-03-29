import pytest

from brownie import Contract, accounts, ZERO_ADDRESS

from typing import NamedTuple, Tuple


from tests.support.quantized_decimal import QuantizedDecimal as D
from tests.support.quantized_decimal_38 import QuantizedDecimal as D2
from tests.support.quantized_decimal_100 import QuantizedDecimal as D3
from tests.support.types import (
    ECLPMathParams,
    ECLPMathParamsQD,
    ECLPPoolParams,
    GyroECLPMathDerivedParams,
    ThreePoolParams,
    TwoPoolBaseParams,
    TwoPoolParams,
    ThreePoolFactoryCreateParams,
    TwoPoolFactoryCreateParams,
    ECLPFactoryCreateParams,
)

from tests.geclp import eclp_prec_implementation
from tests.support.utils import scale
from scripts.utils import format_to_bytes

TOKENS_PER_USER = 1000 * 10**18

DEFAULT_PROTOCOL_FEE = scale("0.2")

# This will provide assertion introspection for common test functions defined in this module.
pytest.register_assert_rewrite("tests.geclp.util", "tests.g3clp.util")


@pytest.fixture(scope="session")
def admin(accounts):
    return accounts[0]


@pytest.fixture(scope="session")
def users(accounts):
    return (accounts[1], accounts[2])


@pytest.fixture(scope="session")
def alice(accounts):
    return accounts[1]


@pytest.fixture(scope="session")
def bob(accounts):
    return accounts[2]


@pytest.fixture(scope="module")
def gyro_two_math_testing(admin, Gyro2CLPMathTesting):
    return admin.deploy(Gyro2CLPMathTesting)


@pytest.fixture(scope="module")
def gyro_eclp_math_testing(admin, GyroECLPMathTesting, GyroECLPMath):
    admin.deploy(GyroECLPMath)
    return admin.deploy(GyroECLPMathTesting)


@pytest.fixture(scope="module")
def gyro_three_math_testing(admin, Gyro3CLPMathTesting):
    return admin.deploy(Gyro3CLPMathTesting)


class ContractAsPureWrapper:
    """Allows using a contract in places where a library of pure functions is expected, for easy debugging or gas measurement.

    Example: ContractAsPureWrapper(GyroMathDebug), then use where GyroMathTesting is expected.
    """

    def __init__(self, contract, prefix="_"):
        self.contract = contract
        self.prefix = prefix

    def __getattr__(self, item):
        item = self.prefix + item
        m = getattr(self.contract, item)

        def f(*args, **kwargs):
            tx = m(*args, **kwargs)
            return tx.return_value

        return f


@pytest.fixture(scope="module")
def gyro_three_math_debug_as_testing(admin, gyro_three_math_debug):
    return ContractAsPureWrapper(gyro_three_math_debug)


@pytest.fixture(scope="module")
def deployed_query_processor(admin, QueryProcessor):
    admin.deploy(QueryProcessor)


@pytest.fixture(scope="module")
def mock_gyro_config(admin, MockGyroConfig):
    # Set some default values.
    ret = admin.deploy(MockGyroConfig)

    formatted_key = format_to_bytes("PROTOCOL_SWAP_FEE_PERC", 32, output_hex=True)
    ret.setUint(formatted_key, DEFAULT_PROTOCOL_FEE, {"from": admin})
    return ret


@pytest.fixture
def gyro_erc20_empty(admin, SimpleERC20):
    return (admin.deploy(SimpleERC20), admin.deploy(SimpleERC20))


@pytest.fixture
def gyro_erc20_empty3(admin, SimpleERC20):
    return tuple(admin.deploy(SimpleERC20) for _ in range(3))


@pytest.fixture
def gyro_erc20_funded(admin, SimpleERC20, users):
    gyro_erc20_0 = admin.deploy(SimpleERC20)
    gyro_erc20_1 = admin.deploy(SimpleERC20)

    gyro_erc20_0.mint(users[0], TOKENS_PER_USER)
    gyro_erc20_1.mint(users[0], TOKENS_PER_USER)
    gyro_erc20_0.mint(users[1], TOKENS_PER_USER)
    gyro_erc20_1.mint(users[1], TOKENS_PER_USER)

    # tokens must be ordered when deploying the Gyro2CLPPool
    if gyro_erc20_0.address.lower() < gyro_erc20_1.address.lower():
        return (gyro_erc20_0, gyro_erc20_1)
    else:
        return (gyro_erc20_1, gyro_erc20_0)


@pytest.fixture
def gyro_erc20_funded3(admin, SimpleERC20, users):
    npools = 3
    gyro_erc20s = [admin.deploy(SimpleERC20) for _ in range(npools)]
    for i in range(2):
        for gyro_erc20 in gyro_erc20s:
            gyro_erc20.mint(users[i], TOKENS_PER_USER)
    gyro_erc20s.sort(key=lambda p: p.address.lower())
    return tuple(gyro_erc20s)


@pytest.fixture(scope="module")
def authorizer(admin, Authorizer):
    return admin.deploy(Authorizer, admin)


@pytest.fixture
def mock_vault(admin, MockVault, authorizer):
    return admin.deploy(MockVault, authorizer)


@pytest.fixture(scope="module")
def balancer_vault(admin, BalancerVault, SimpleERC20, authorizer):
    weth9 = admin.deploy(SimpleERC20)
    return admin.deploy(BalancerVault, authorizer.address, weth9.address, 0, 0)


@pytest.fixture
def balancer_vault_pool(
    admin,
    Gyro2CLPPool,
    gyro_erc20_funded,
    balancer_vault,
    mock_gyro_config,
    deployed_query_processor,
):
    args = TwoPoolParams(
        baseParams=TwoPoolBaseParams(
            vault=balancer_vault.address,
            name="Gyro2CLPPool",  # string
            symbol="GTP",  # string
            token0=gyro_erc20_funded[0].address,  # IERC20
            token1=gyro_erc20_funded[1].address,  # IERC20
            swapFeePercentage=1 * 10**15,  # 0.5%
            pauseWindowDuration=0,  # uint256
            bufferPeriodDuration=0,  # uint256
            owner=admin,  # address
        ),
        sqrtAlpha=D("0.97") * 10**18,  # uint256
        sqrtBeta=D("1.02") * 10**18,  # uint256
    )
    return admin.deploy(Gyro2CLPPool, args, mock_gyro_config.address)


@pytest.fixture
def mock_vault_pool(
    admin,
    Gyro2CLPPool,
    gyro_erc20_funded,
    mock_vault,
    mock_gyro_config,
    deployed_query_processor,
):
    args = TwoPoolParams(
        baseParams=TwoPoolBaseParams(
            vault=mock_vault.address,
            name="Gyro2CLPPool",  # string
            symbol="GTP",  # string
            token0=gyro_erc20_funded[0].address,  # IERC20
            token1=gyro_erc20_funded[1].address,  # IERC20
            swapFeePercentage=D(1) * 10**15,
            pauseWindowDuration=0,  # uint256
            bufferPeriodDuration=0,  # uint256
            owner=admin,  # address
        ),
        sqrtAlpha=D("0.97") * 10**18,  # uint256
        sqrtBeta=D("1.02") * 10**18,  # uint256
    )
    return admin.deploy(Gyro2CLPPool, args, mock_gyro_config.address)


@pytest.fixture
def mock_pool_from_factory(
    admin,
    Gyro2CLPPoolFactory,
    Gyro2CLPPool,
    mock_vault,
    mock_gyro_config,
    gyro_erc20_funded,
    deployed_query_processor,
):
    factory = admin.deploy(Gyro2CLPPoolFactory, mock_vault, mock_gyro_config.address)

    args = TwoPoolFactoryCreateParams(
        name="Gyro2CLPPoolFromFactory",
        symbol="G2PF",
        tokens=[gyro_erc20_funded[i].address for i in range(2)],
        sqrts=[D("0.97") * 10**18, D("1.02") * 10**18],
        rate_providers=[ZERO_ADDRESS, ZERO_ADDRESS],
        swapFeePercentage=D(1) * 10**15,
        owner=admin,
    )

    tx = factory.create(*args)
    pool_address = tx.events["PoolCreated"]["pool"]
    pool_from_factory = Contract.from_abi(
        "Gyro2CLPPool", pool_address, Gyro2CLPPool.abi
    )

    return pool_from_factory


@pytest.fixture
def rate_scaled_2clp_pool(
    admin,
    Gyro2CLPPool,
    gyro_erc20_funded,
    mock_vault,
    mock_gyro_config,
    deployed_query_processor,
    mock_rate_provider,
):
    """2CLP with rate scaling enabled for asset x"""
    args = TwoPoolParams(
        baseParams=TwoPoolBaseParams(
            vault=mock_vault.address,
            name="RateScaledGyro2CLPPool",  # string
            symbol="RSGTP",  # string
            token0=gyro_erc20_funded[0].address,  # IERC20
            token1=gyro_erc20_funded[1].address,  # IERC20
            swapFeePercentage=D(1) * 10**15,
            pauseWindowDuration=0,  # uint256
            bufferPeriodDuration=0,  # uint256
            owner=admin,  # address
        ),
        sqrtAlpha=D("0.97") * 10**18,  # uint256
        sqrtBeta=D("1.02") * 10**18,  # uint256
        rateProvider0=mock_rate_provider,
        rateProvider1=ZERO_ADDRESS,
    )
    return admin.deploy(Gyro2CLPPool, args, mock_gyro_config.address)


@pytest.fixture
def rate_scaled_2clp_pool_from_factory(
    admin,
    Gyro2CLPPoolFactory,
    Gyro2CLPPool,
    mock_vault,
    mock_gyro_config,
    gyro_erc20_funded,
    deployed_query_processor,
    mock_rate_provider,
):
    factory = admin.deploy(Gyro2CLPPoolFactory, mock_vault, mock_gyro_config.address)

    args = TwoPoolFactoryCreateParams(
        name="RateScaledGyro2CLPPoolFromFactory",
        symbol="RSG2PF",
        tokens=[gyro_erc20_funded[i].address for i in range(2)],
        sqrts=[D("0.97") * 10**18, D("1.02") * 10**18],
        rate_providers=[mock_rate_provider.address, ZERO_ADDRESS],
        swapFeePercentage=D(1) * 10**15,
        owner=admin,
    )

    tx = factory.create(*args)
    pool_address = tx.events["PoolCreated"]["pool"]
    pool_from_factory = Contract.from_abi(
        "Gyro2CLPPool", pool_address, Gyro2CLPPool.abi
    )

    return pool_from_factory


@pytest.fixture
def mock_vault_pool3(
    admin, Gyro3CLPPool, gyro_erc20_funded3, mock_vault, mock_gyro_config
):
    args = ThreePoolParams(
        vault=mock_vault.address,
        config_address=mock_gyro_config.address,
        config=ThreePoolFactoryCreateParams(
            name="Gyro3CLPPool",  # string
            symbol="G3P",  # string
            tokens=[gyro_erc20_funded3[i].address for i in range(3)],
            swapFeePercentage=D(1) * 10**15,
            owner=admin,  # address
            root3Alpha=D("0.97") * 10**18,
        ),
    )
    return admin.deploy(Gyro3CLPPool, args)


@pytest.fixture
def mock_pool3_from_factory(
    admin,
    Gyro3CLPPoolFactory,
    Gyro3CLPPool,
    mock_vault,
    mock_gyro_config,
    gyro_erc20_funded3,
):
    factory = admin.deploy(Gyro3CLPPoolFactory, mock_vault, mock_gyro_config.address)

    args = ThreePoolFactoryCreateParams(
        name="Gyro3CLPPoolFromFactory",
        symbol="G3PF",
        tokens=[gyro_erc20_funded3[i].address for i in range(3)],
        root3Alpha=D("0.97") * 10**18,
        swapFeePercentage=D(1) * 10**15,
        owner=admin,
    )

    tx = factory.create(args)
    pool_address = tx.events["PoolCreated"]["pool"]
    pool3_from_factory = Contract.from_abi(
        "Gyro3CLPPool", pool_address, Gyro3CLPPool.abi
    )

    return pool3_from_factory


@pytest.fixture
def balancer_vault_pool3(
    admin,
    Gyro3CLPPool,
    gyro_erc20_funded3,
    balancer_vault,
    mock_gyro_config,
):
    args = ThreePoolParams(
        vault=balancer_vault.address,
        config_address=mock_gyro_config.address,
        config=ThreePoolFactoryCreateParams(
            name="Gyro3CLPPool",  # string
            symbol="G3P",  # string
            tokens=[gyro_erc20_funded3[i].address for i in range(3)],
            swapFeePercentage=D(1) * 10**15,
            owner=admin,  # address
            root3Alpha=D("0.97") * 10**18,
        ),
    )
    return admin.deploy(Gyro3CLPPool, args)


@pytest.fixture(scope="module")
def math_testing(admin, MathTesting):
    return admin.deploy(MathTesting)


@pytest.fixture(scope="module")
def signed_math_testing(admin, SignedMathTesting):
    return admin.deploy(SignedMathTesting)


@pytest.fixture(scope="module")
def gyro_fixed_point_testing(admin, GyroFixedPointTesting):
    return admin.deploy(GyroFixedPointTesting)


@pytest.fixture(scope="module")
def pool_factory(admin, Gyro2CLPPoolFactory, gyro_config):
    return admin.deploy(Gyro2CLPPoolFactory, balancer_vault, gyro_config.address)


@pytest.fixture
def eclp_pool(
    admin,
    GyroECLPPool,
    GyroECLPMath,
    gyro_erc20_funded,
    mock_vault,
    mock_gyro_config,
    deployed_query_processor,
):
    """ECLP pool *without* rate scaling (disabled)."""
    admin.deploy(GyroECLPMath)
    two_pool_base_params = TwoPoolBaseParams(
        vault=mock_vault.address,
        name="GyroECLPTwoPool",  # string
        symbol="GCTP",  # string
        token0=gyro_erc20_funded[0].address,  # IERC20
        token1=gyro_erc20_funded[1].address,  # IERC20
        swapFeePercentage=1 * 10**15,  # 0.5%
        pauseWindowDuration=0,  # uint256
        bufferPeriodDuration=0,  # uint256
        owner=admin,  # address
    )

    eclp_params = ECLPMathParamsQD(
        alpha=D("0.97"),
        beta=D("1.02"),
        c=D("0.7071067811865475244"),
        s=D("0.7071067811865475244"),
        l=D("2"),
    )
    derived_eclp_params = eclp_prec_implementation.calc_derived_values(eclp_params)
    args = ECLPPoolParams(
        two_pool_base_params,
        eclp_params.scale(),
        derived_eclp_params.scale(),
    )
    return admin.deploy(
        GyroECLPPool, args, mock_gyro_config.address, gas_limit=11250000
    )


@pytest.fixture
def mock_eclp_pool_from_factory(
    admin,
    GyroECLPPoolFactory,
    GyroECLPPool,
    GyroECLPMath,
    mock_vault,
    mock_gyro_config,
    gyro_erc20_funded,
    deployed_query_processor,
):
    admin.deploy(GyroECLPMath)
    factory = admin.deploy(GyroECLPPoolFactory, mock_vault, mock_gyro_config.address)

    eclp_params = ECLPMathParamsQD(
        alpha=D("0.97"),
        beta=D("1.02"),
        c=D("0.7071067811865475244"),
        s=D("0.7071067811865475244"),
        l=D("2"),
    )
    derived_eclp_params = eclp_prec_implementation.calc_derived_values(eclp_params)

    args = ECLPFactoryCreateParams(
        name="GyroECLPTwoPool",  # string
        symbol="GCTP",  # string
        tokens=[gyro_erc20_funded[i].address for i in range(2)],
        params=eclp_params.scale(),
        derived_params=derived_eclp_params.scale(),
        rate_providers=[ZERO_ADDRESS, ZERO_ADDRESS],
        swap_fee_percentage=1 * 10**15,
        owner=admin,  # address
    )

    tx = factory.create(*args)
    pool_address = tx.events["PoolCreated"]["pool"]
    pool_from_factory = Contract.from_abi(
        "GyroECLPPool", pool_address, GyroECLPPool.abi
    )

    return pool_from_factory


@pytest.fixture
def rate_scaled_eclp_pool(
    admin,
    GyroECLPPool,
    GyroECLPMath,
    gyro_erc20_funded,
    mock_vault,
    mock_gyro_config,
    deployed_query_processor,
    mock_rate_provider,
):
    """ECLP with rate scaling enabled for asset x"""
    admin.deploy(GyroECLPMath)
    two_pool_base_params = TwoPoolBaseParams(
        vault=mock_vault.address,
        name="RateScaledGyroECLPTwoPool",  # string
        symbol="RSGCTP",  # string
        token0=gyro_erc20_funded[0].address,  # IERC20
        token1=gyro_erc20_funded[1].address,  # IERC20
        swapFeePercentage=D("0.001e18"),
        pauseWindowDuration=0,  # uint256
        bufferPeriodDuration=0,  # uint256
        owner=admin,  # address
    )

    eclp_params = ECLPMathParamsQD(
        alpha=D("0.97"),
        beta=D("1.02"),
        c=D("0.7071067811865475244"),
        s=D("0.7071067811865475244"),
        l=D("2"),
    )
    derived_eclp_params = eclp_prec_implementation.calc_derived_values(eclp_params)
    eclp_pool_args = ECLPPoolParams(
        two_pool_base_params,
        eclp_params.scale(),
        derived_eclp_params.scale(),
        rateProvider0=mock_rate_provider,
        rateProvider1=ZERO_ADDRESS,
    )

    # Token 0 is scaled by mock_rate_provider, token 1 is unscaled.
    return admin.deploy(
        GyroECLPPool,
        eclp_pool_args,
        mock_gyro_config.address,
        gas_limit=11250000,
    )


@pytest.fixture
def mock_rate_scaled_eclp_pool_from_factory(
    admin,
    GyroECLPPoolFactory,
    GyroECLPPool,
    GyroECLPMath,
    mock_vault,
    mock_gyro_config,
    mock_rate_provider,
    gyro_erc20_funded,
    deployed_query_processor,
):
    admin.deploy(GyroECLPMath)
    factory = admin.deploy(GyroECLPPoolFactory, mock_vault, mock_gyro_config.address)

    eclp_params = ECLPMathParamsQD(
        alpha=D("0.97"),
        beta=D("1.02"),
        c=D("0.7071067811865475244"),
        s=D("0.7071067811865475244"),
        l=D("2"),
    )
    derived_eclp_params = eclp_prec_implementation.calc_derived_values(eclp_params)

    args = ECLPFactoryCreateParams(
        name="RateScaledGyroECLPTwoPool",  # string
        symbol="RSGCTP",  # string
        tokens=[gyro_erc20_funded[i].address for i in range(2)],
        params=eclp_params.scale(),
        derived_params=derived_eclp_params.scale(),
        rate_providers=[mock_rate_provider.address, ZERO_ADDRESS],
        swap_fee_percentage=1 * 10**15,
        owner=admin,  # address
    )

    tx = factory.create(*args)
    pool_address = tx.events["PoolCreated"]["pool"]
    pool_from_factory = Contract.from_abi(
        "GyroECLPPool", pool_address, GyroECLPPool.abi
    )

    return pool_from_factory


@pytest.fixture
def mock_rate_provider(admin, MockRateProvider):
    c = admin.deploy(MockRateProvider)
    c.mockRate(scale("1.5"))
    return c


@pytest.fixture(autouse=True)
def isolation(fn_isolation):
    pass


class Params(NamedTuple):
    alpha: D
    beta: D
    c: D
    s: D
    l: D


class DerivedParams(NamedTuple):
    tauAlpha: Tuple[D2, D2]
    tauBeta: Tuple[D2, D2]
    u: D2
    v: D2
    w: D2
    z: D2
    dSq: D2
    # dAlpha: D2
    # dBeta: D2


def scale_eclp_params(p: Params) -> Params:
    params = Params(
        alpha=p.alpha * D("1e18"),
        beta=p.beta * D("1e18"),
        c=p.c * D("1e18"),
        s=p.s * D("1e18"),
        l=p.l * D("1e18"),
    )
    return params


class Vector2(NamedTuple):
    x: D2
    y: D2


def scale_derived_values(d: DerivedParams) -> DerivedParams:
    derived = DerivedParams(
        tauAlpha=Vector2(d.tauAlpha[0] * D2("1e38"), d.tauAlpha[1] * D2("1e38")),
        tauBeta=Vector2(d.tauBeta[0] * D2("1e38"), d.tauBeta[1] * D2("1e38")),
        u=d.u * D2("1e38"),
        v=d.v * D2("1e38"),
        w=d.w * D2("1e38"),
        z=d.z * D2("1e38"),
        dSq=d.dSq * D2("1e38"),
        # dAlpha=d.dAlpha * D2("1e38"),
        # dBeta=d.dBeta * D2("1e38"),
    )
    return derived
