import pytest
from brownie.test.managers.runner import RevertContextManager as reverts

from tests.support.quantized_decimal import QuantizedDecimal as D
from tests.support.types import TwoPoolBaseParams, TwoPoolParams


@pytest.fixture(scope="module")
def pool_owner(PoolOwner, admin):
    return admin.deploy(PoolOwner)


@pytest.fixture
def mock_pool(
    admin,
    Gyro2CLPPool,
    gyro_erc20_funded,
    balancer_vault,
    mock_gyro_config,
    deployed_query_processor,
    pool_owner,
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
            owner=pool_owner,  # address
        ),
        sqrtAlpha=D("0.97") * 10**18,  # uint256
        sqrtBeta=D("1.02") * 10**18,  # uint256
    )
    return admin.deploy(Gyro2CLPPool, args, mock_gyro_config.address)


def test_add_swap_fee_manager(accounts, pool_owner):
    assert pool_owner.listFeeManagers() == []
    pool_owner.addSwapFeeManager(accounts[1])
    assert pool_owner.listFeeManagers() == [accounts[1]]

    with reverts("Ownable: caller is not the owner"):
        pool_owner.addSwapFeeManager(accounts[2], {"from": accounts[2]})


def test_remove_swap_fee_manager(accounts, pool_owner):
    pool_owner.addSwapFeeManager(accounts[1])
    pool_owner.addSwapFeeManager(accounts[2])
    assert pool_owner.listFeeManagers() == [accounts[1], accounts[2]]
    pool_owner.removeSwapFeeManager(accounts[1])
    assert pool_owner.listFeeManagers() == [accounts[2]]

    with reverts("Ownable: caller is not the owner"):
        pool_owner.removeSwapFeeManager(accounts[2], {"from": accounts[2]})


def test_set_swap_fee(accounts, pool_owner, mock_pool):
    action = mock_pool.setSwapFeePercentage.encode_input(10**15)
    with reverts("PoolOwner: not owner or fee manager"):
        pool_owner.executeAction(mock_pool, action, {"from": accounts[1]})

    pool_owner.executeAction(mock_pool, action)
    assert mock_pool.getSwapFeePercentage() == 10**15

    pool_owner.addSwapFeeManager(accounts[1])
    action = mock_pool.setSwapFeePercentage.encode_input(10**16)
    pool_owner.executeAction(mock_pool, action, {"from": accounts[1]})
    assert mock_pool.getSwapFeePercentage() == 10**16
