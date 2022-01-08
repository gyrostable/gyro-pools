from collections import namedtuple

import pytest

BaseParams = namedtuple(
    "BaseParams",
    [
        "vault",  # IVault
        "name",  # string
        "symbol",  # string
        "token0",  # IERC20
        "token1",  # IERC20
        "normalizedWeight0",  # uint256
        "normalizedWeight1",  # uint256
        "swapFeePercentage",  # uint256
        "pauseWindowDuration",  # uint256
        "bufferPeriodDuration",  # uint256
        "oracleEnabled",  # bool
        "owner",  # address
    ],
)


GyroParams = namedtuple(
    "GyroParams",
    [
        "baseParams",  # BaseParams
        "sqrtAlpha",  # uint256, should already be upscaled
        "sqrtBeta",  # uint256, Should already be upscaled
    ],
)


TOKENS_PER_USER = 1000 * 10 ** 18


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

    gyro_erc20_0.mint(users[0], TOKENS_PER_USER)
    gyro_erc20_1.mint(users[0], TOKENS_PER_USER)
    gyro_erc20_0.mint(users[1], TOKENS_PER_USER)
    gyro_erc20_1.mint(users[1], TOKENS_PER_USER)

    # tokens must be ordered when deploying the GyroTwoPool
    if gyro_erc20_0.address.lower() < gyro_erc20_1.address.lower():
        return (gyro_erc20_0, gyro_erc20_1)
    else:
        return (gyro_erc20_1, gyro_erc20_0)


@pytest.fixture(scope="module")
def math_testing(admin, MathTesting):
    return admin.deploy(MathTesting)


# @pytest.fixture
# def gyro_pool_with_vault_testing(
#     admin,
#     VaultTesting,
#     GyroTwoPool,
#     SimpleERC20,
#     Authorizer,
#     gyro_erc20_funded,
#     QueryProcessor,
# ):
#     weth9 = admin.deploy(SimpleERC20)
#     authorizer = admin.deploy(Authorizer, admin)
#     vault = admin.deploy(VaultTesting, authorizer.address, weth9.address, 0, 0)

#     args = GyroParams(
#         baseParams=BaseParams(
#             vault=vault.address,
#             name="GyroTwoPool",  # string
#             symbol="GTP",  # string
#             token0=gyro_erc20_funded[0].address,  # IERC20
#             token1=gyro_erc20_funded[1].address,  # IERC20
#             normalizedWeight0=0.5 * 10 ** 18,  # uint256
#             normalizedWeight1=0.5 * 10 ** 18,  # uint256
#             swapFeePercentage=1 * 10 ** 15,  # 0.1%
#             pauseWindowDuration=0,  # uint256
#             bufferPeriodDuration=0,  # uint256
#             oracleEnabled=False,  # bool
#             owner=admin,  # address
#         ),
#         sqrtAlpha=0.97 * 10 ** 18,  # uint256
#         sqrtBeta=1.02 * 10 ** 18,  # uint256
#     )
#     admin.deploy(QueryProcessor)
#     gyroTwoPool = admin.deploy(GyroTwoPool, args)
#     return (vault, gyroTwoPool)

@pytest.fixture(scope="module")
def authorizer(admin, Authorizer):
    return admin.deploy(Authorizer, admin)


@pytest.fixture(scope="module")
def vault(admin, MockVault, authorizer):
    return admin.deploy(MockVault, authorizer)


@pytest.fixture
def pool(
    admin, GyroTwoPool, gyro_erc20_funded, vault, QueryProcessor
):
    admin.deploy(QueryProcessor)
    args = GyroParams(
        baseParams=BaseParams(
            vault=vault.address,
            name="GyroTwoPool",  # string
            symbol="GTP",  # string
            token0=gyro_erc20_funded[0].address,  # IERC20
            token1=gyro_erc20_funded[1].address,  # IERC20
            normalizedWeight0=0.6 * 10 ** 18,  # uint256
            normalizedWeight1=0.4 * 10 ** 18,  # uint256
            swapFeePercentage=1 * 10 ** 15,  # 0.5%
            pauseWindowDuration=0,  # uint256
            bufferPeriodDuration=0,  # uint256
            oracleEnabled=False,  # bool
            owner=admin,  # address
        ),
        sqrtAlpha=0.97 * 10 ** 18,  # uint256
        sqrtBeta=1.02 * 10 ** 18,  # uint256
    )
    return admin.deploy(GyroTwoPool, args)


@pytest.fixture
def pool_factory(admin, GyroTwoPoolFactory):
    return admin.deploy(GyroTwoPoolFactory, vault)
