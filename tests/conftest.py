from tests.support.quantized_decimal import QuantizedDecimal as D
import pytest

from tests.support.types import TwoPoolBaseParams, TwoPoolParams, ThreePoolParams

TOKENS_PER_USER = 1000 * 10**18

# This will provide assertion introspection for common test functions defined in this module.
pytest.register_assert_rewrite("tests.cemm.util", "tests.cpmmv3.util")


@pytest.fixture(scope="module")
def admin(accounts):
    return accounts[0]


@pytest.fixture(scope="module")
def users(accounts):
    return (accounts[1], accounts[2])


@pytest.fixture(scope="module")
def gyro_two_math_testing(admin, GyroTwoMathTesting):
    return admin.deploy(GyroTwoMathTesting)


@pytest.fixture(scope="module")
def gyro_cemm_math_testing(admin, GyroCEMMMathTesting):
    return admin.deploy(GyroCEMMMathTesting)


@pytest.fixture(scope="module")
def gyro_three_math_testing(admin, GyroThreeMathTesting):
    return admin.deploy(GyroThreeMathTesting)


@pytest.fixture(scope="module")
def gyro_three_math_debug(admin, GyroThreeMathDebug):
    return admin.deploy(GyroThreeMathDebug)

class ContractAsPureWrapper:
    """Allows using a contract in places where a library of pure functions is expected, for easy debugging or gas measurement.

    Example: ContractAsPureWrapper(GyroMathDebug), then use where GyroMathTesting is expected."""
    def __init__(self, contract, prefix = '_'):
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
def mock_gyro_config(admin, MockGyroConfig):
    return admin.deploy(MockGyroConfig)

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

    # tokens must be ordered when deploying the GyroTwoPool
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
    GyroTwoPool,
    gyro_erc20_funded,
    balancer_vault,
    QueryProcessor,
    mock_gyro_config,
):
    admin.deploy(QueryProcessor)
    args = TwoPoolParams(
        baseParams=TwoPoolBaseParams(
            vault=balancer_vault.address,
            name="GyroTwoPool",  # string
            symbol="GTP",  # string
            token0=gyro_erc20_funded[0].address,  # IERC20
            token1=gyro_erc20_funded[1].address,  # IERC20
            normalizedWeight0=D("0.6") * 10**18,  # uint256
            normalizedWeight1=D("0.4") * 10**18,  # uint256
            swapFeePercentage=1 * 10**15,  # 0.5%
            pauseWindowDuration=0,  # uint256
            bufferPeriodDuration=0,  # uint256
            oracleEnabled=False,  # bool
            owner=admin,  # address
        ),
        sqrtAlpha=D("0.97") * 10**18,  # uint256
        sqrtBeta=D("1.02") * 10**18,  # uint256
    )
    return admin.deploy(GyroTwoPool, args, mock_gyro_config.address)

@pytest.fixture
def mock_vault_pool(
    admin, GyroTwoPool, gyro_erc20_funded, mock_vault, QueryProcessor, mock_gyro_config
):
    admin.deploy(QueryProcessor)
    args = TwoPoolParams(
        baseParams=TwoPoolBaseParams(
            vault=mock_vault.address,
            name="GyroTwoPool",  # string
            symbol="GTP",  # string
            token0=gyro_erc20_funded[0].address,  # IERC20
            token1=gyro_erc20_funded[1].address,  # IERC20
            normalizedWeight0=D("0.6") * 10**18,  # uint256
            normalizedWeight1=D("0.4") * 10**18,  # uint256
            swapFeePercentage=D(1) * 10**15,
            pauseWindowDuration=0,  # uint256
            bufferPeriodDuration=0,  # uint256
            oracleEnabled=False,  # bool
            owner=admin,  # address
        ),
        sqrtAlpha=D("0.97") * 10**18,  # uint256
        sqrtBeta=D("1.02") * 10**18,  # uint256
    )
    return admin.deploy(GyroTwoPool, args, mock_gyro_config.address)

@pytest.fixture
def mock_vault_pool3(
    admin, GyroThreePool, gyro_erc20_funded3, mock_vault, QueryProcessor, mock_gyro_config
):
    admin.deploy(QueryProcessor)
    args = ThreePoolParams(
        vault=mock_vault.address,
        name="GyroThreePool",  # string
        symbol="G3P",  # string
        tokens=[gyro_erc20_funded3[i].address for i in range(3)],
        assetManagers=["0x0000000000000000000000000000000000000000"] * 3,
        swapFeePercentage=D(1) * 10**15,
        pauseWindowDuration=0,  # uint256
        bufferPeriodDuration=0,  # uint256
        owner=admin,  # address
        root3Alpha=D("0.97") * 10**18,
    )
    return admin.deploy(GyroThreePool, *args, mock_gyro_config.address)

@pytest.fixture
def balancer_vault_pool3(
    admin,
    GyroThreePool,
    gyro_erc20_funded3,
    balancer_vault,
    QueryProcessor,
    mock_gyro_config,
):
    admin.deploy(QueryProcessor)
    args = ThreePoolParams(
        vault=balancer_vault.address,
        name="GyroThreePool",  # string
        symbol="G3P",  # string
        tokens=[gyro_erc20_funded3[i].address for i in range(3)],
        assetManagers=["0x0000000000000000000000000000000000000000"] * 3,
        swapFeePercentage=D(1) * 10**15,
        pauseWindowDuration=0,  # uint256
        bufferPeriodDuration=0,  # uint256
        owner=admin,  # address
        root3Alpha=D("0.97") * 10**18,
    )
    return admin.deploy(GyroThreePool, *args, mock_gyro_config.address)


@pytest.fixture(scope="module")
def math_testing(admin, MathTesting):
    return admin.deploy(MathTesting)


@pytest.fixture(scope="module")
def signed_math_testing(admin, SignedMathTesting):
    return admin.deploy(SignedMathTesting)


@pytest.fixture(scope="module")
def mock_gyro_two_oracle_math(admin, MockGyroTwoOracleMath):
    return admin.deploy(MockGyroTwoOracleMath)


@pytest.fixture(scope="module")
def gyro_cemm_oracle_math_testing(admin, GyroCEMMOracleMathTesting):
    return admin.deploy(GyroCEMMOracleMathTesting)


@pytest.fixture(scope="module")
def pool_factory(admin, GyroTwoPoolFactory, gyro_config):
    return admin.deploy(GyroTwoPoolFactory, balancer_vault, gyro_config.address)


@pytest.fixture(autouse=True)
def isolation(fn_isolation):
    pass
