import pytest

from tests.support.quantized_decimal import QuantizedDecimal as D
from tests.support.types import (
    CEMMMathParams,
    CEMMPoolParams,
    GyroCEMMMathDerivedParams,
    ThreePoolParams,
    TwoPoolBaseParams,
    TwoPoolParams,
)

TOKENS_PER_USER = 1000 * 10**18

# This will provide assertion introspection for common test functions defined in this module.
pytest.register_assert_rewrite("tests.cemm.util")


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
    mock_gyro_config,
):
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
    admin, GyroTwoPool, gyro_erc20_funded, mock_vault, mock_gyro_config
):
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
    admin,
    GyroThreePool,
    gyro_erc20_funded3,
    mock_vault,
    mock_gyro_config,
):
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
    mock_gyro_config,
):
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


@pytest.fixture
def cemm_pool(
    admin,
    GyroCEMMPool,
    gyro_erc20_funded,
    balancer_vault,
    mock_gyro_config,
    QueryProcessor,
):
    admin.deploy(QueryProcessor)
    two_pool_base_params = TwoPoolBaseParams(
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
    )

    cemm_params = CEMMMathParams(
        alpha=D("0.97") * 10**18,
        beta=D("1.02") * 10**18,
        c=D("0.2") * 10**18,
        s=D("0.1") * 10**18,
        l=D("2") * 10**18,
    )
    derived_cemm_params = calc_derived_values(cemm_params)
    args = CEMMPoolParams(two_pool_base_params, cemm_params, derived_cemm_params)
    return admin.deploy(GyroCEMMPool, args, mock_gyro_config.address)


@pytest.fixture(autouse=True)
def isolation(fn_isolation):
    pass


def calc_derived_values(p: CEMMMathParams):
    s, c, lam, alpha, beta = (
        D(p.s).raw,
        D(p.c).raw,
        D(p.l).raw,
        D(p.alpha).raw,
        D(p.beta).raw,
    )
    s, c, lam, alpha, beta = (
        D(s),
        D(c),
        D(lam),
        D(alpha),
        D(beta),
    )
    dSq = c * c + s * s
    d = dSq.sqrt()
    dAlpha = D(1) / (
        ((c / d + alpha * s / d) ** 2 / lam**2 + (alpha * c / d - s / d) ** 2).sqrt()
    )
    dBeta = D(1) / (
        ((c / d + beta * s / d) ** 2 / lam**2 + (beta * c / d - s / d) ** 2).sqrt()
    )
    tauAlpha = [0, 0]
    tauAlpha[0] = (alpha * c - s) * dAlpha
    tauAlpha[1] = (c + s * alpha) * dAlpha / lam

    tauBeta = [0, 0]
    tauBeta[0] = (beta * c - s) * dBeta
    tauBeta[1] = (c + s * beta) * dBeta / lam

    w = s * c * (tauBeta[1] - tauAlpha[1])
    z = c * c * tauBeta[0] + s * s * tauAlpha[0]
    u = s * c * (tauBeta[0] - tauAlpha[0])
    v = s * s * tauBeta[1] + c * c * tauAlpha[1]

    tauAlpha38 = (D(tauAlpha[0].raw), D(tauAlpha[1].raw))
    tauBeta38 = (D(tauBeta[0].raw), D(tauBeta[1].raw))
    derived = GyroCEMMMathDerivedParams(
        tauAlpha=(tauAlpha38[0], tauAlpha38[1]),
        tauBeta=(tauBeta38[0], tauBeta38[1]),
        u=D(u.raw),
        v=D(v.raw),
        w=D(w.raw),
        z=D(z.raw),
        dSq=D(dSq.raw),
        # dAlpha=D(dAlpha.raw),
        # dBeta=D(dBeta.raw),
    )
    return derived
