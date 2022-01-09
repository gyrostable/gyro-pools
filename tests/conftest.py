from collections import namedtuple

import pytest

BaseParams = namedtuple(
    "BaseParams",
    [
        "vault",  #  IVault
        "name",  #  string
        "symbol",  #  string
        "token0",  #  IERC20
        "token1",  #  IERC20
        "normalizedWeight0",  #  uint256 ; // A: For now we leave it, unclear if we will need it
        "normalizedWeight1",  #  uint256 ; // A: For now we leave it, unclear if we will need it
        "swapFeePercentage",  #  uint256
        "pauseWindowDuration",  #  uint256
        "bufferPeriodDuration",  #  uint256
        "oracleEnabled",  #  bool
        "owner",  #  address
    ],
)


GyroParams = namedtuple(
    "GyroParams",
    [
        "baseParams",  #  BaseParams
        "sqrtAlpha",  #  uint256          // A: Should already be upscaled
        "sqrtBeta",  #  uint256           // A: Should already be upscaled. Could be passed as an array[](2)
    ],
)


gyro_tokensPerUser = 1000 * 10 ** 18


@pytest.fixture(scope="module")
def admin(accounts):
    return accounts[0]


@pytest.fixture(scope="module")
def users(accounts):
    return (accounts[1], accounts[2])


@pytest.fixture
def gyro_two_math_testing(admin, GyroTwoMathTesting):
    return admin.deploy(GyroTwoMathTesting)


@pytest.fixture
def gyro_erc20_empty(admin, SimpleERC20):
    return (admin.deploy(SimpleERC20), admin.deploy(SimpleERC20))


@pytest.fixture
def gyro_erc20_funded(admin, SimpleERC20, users):
    gyro_erc20_0 = admin.deploy(SimpleERC20)
    gyro_erc20_1 = admin.deploy(SimpleERC20)

    gyro_erc20_0.mint(users[0], gyro_tokensPerUser)
    gyro_erc20_1.mint(users[0], gyro_tokensPerUser)
    gyro_erc20_0.mint(users[1], gyro_tokensPerUser)
    gyro_erc20_1.mint(users[1], gyro_tokensPerUser)

    # tokens must be ordered when deploying the GyroTwoPool
    if gyro_erc20_0.address.lower() < gyro_erc20_1.address.lower():
        return (gyro_erc20_0, gyro_erc20_1)
    else:
        return (gyro_erc20_1, gyro_erc20_0)


@pytest.fixture
def gyro_pool_testing(
    admin,
    VaultTesting,
    GyroTwoPool,
    SimpleERC20,
    Authorizer,
    gyro_erc20_funded,
    QueryProcessor,
):
    weth9 = admin.deploy(SimpleERC20)
    authorizer = admin.deploy(Authorizer, admin)
    vault = admin.deploy(VaultTesting, authorizer.address, weth9.address, 0, 0)

    args = GyroParams(
        baseParams=BaseParams(
            vault=vault.address,
            name="GyroTwoPool",  #  string
            symbol="GTP",  #  string
            token0=gyro_erc20_funded[0].address,  #  IERC20
            token1=gyro_erc20_funded[1].address,  #  IERC20
            normalizedWeight0=0.5 * 10 ** 18,  #  uint256 ;
            normalizedWeight1=0.5 * 10 ** 18,  #  uint256 ;
            swapFeePercentage=1 * 10 ** 15,  # 0.1%
            pauseWindowDuration=0,  #  uint256
            bufferPeriodDuration=0,  #  uint256
            oracleEnabled=False,  #  bool
            owner=admin,  #  address
        ),
        sqrtAlpha=0.97 * 10 ** 18,  #  uint256
        sqrtBeta=1.02 * 10 ** 18,  #  uint256
    )
    admin.deploy(QueryProcessor)
    gyroTwoPool = admin.deploy(GyroTwoPool, args)
    return (vault, gyroTwoPool)


@pytest.fixture
def gyro_poolMockVault_testing(
    admin, MockVault, GyroTwoPool, SimpleERC20, Authorizer, gyro_erc20_funded
):
    authorizer = admin.deploy(Authorizer, admin)

    vault = admin.deploy(MockVault, authorizer)

    args = GyroParams(
        baseParams=BaseParams(
            vault=vault.address,
            name="GyroTwoPool",  #  string
            symbol="GTP",  #  string
            token0=gyro_erc20_funded[0].address,  #  IERC20
            token1=gyro_erc20_funded[1].address,  #  IERC20
            normalizedWeight0=0.6 * 10 ** 18,  #  uint256 ;
            normalizedWeight1=0.4 * 10 ** 18,  #  uint256 ;
            swapFeePercentage=1 * 10 ** 15,  #  0.5%
            pauseWindowDuration=0,  #  uint256
            bufferPeriodDuration=0,  #  uint256
            oracleEnabled=False,  #  bool
            owner=admin,  #  address
        ),
        sqrtAlpha=0.97 * 10 ** 18,  #  uint256
        sqrtBeta=1.02 * 10 ** 18,  #  uint256
    )
    gyroTwoPool = admin.deploy(GyroTwoPool, args)
    return (vault, gyroTwoPool)


##@pytest.fixture
##def gyro_factory_testing(admin, GyroTwoFactory, gyro_vault_testing):
##    return admin.deploy(GyroTwoFactory,gyro_vault_testing.address)
##    return admin
#    return admin.deploy(GyroTwoFactory, "0x8f7F78080219d4066A8036ccD30D588B416a40DB", ["0x8f7F78080219d4066A8036ccD30D588B416a40DB","0x8f7F78080219d4066A8036ccD30D588B416a40DB"])


@pytest.fixture(scope="module")
def math_testing(admin, MathTesting):
    return admin.deploy(MathTesting)


@pytest.fixture(scope="module")
def mock_gyro_two_oracle_math(admin, MockGyroTwoOracleMath):
    return admin.deploy(MockGyroTwoOracleMath)
