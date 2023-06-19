import pytest

from eth_utils import keccak
from eth_abi import encode_abi

from tests.conftest import DEFAULT_PROTOCOL_FEE


@pytest.mark.parametrize(
    "setting,method,initial_value",
    (
        (b"PROTOCOL_SWAP_FEE_PERC", "getSwapFeePercForPool", DEFAULT_PROTOCOL_FEE),
        (b"PROTOCOL_FEE_GYRO_PORTION", "getProtocolFeeGyroPortionForPool", 1e18),
    ),
)
def test_get_fee_config(mock_gyro_config, setting, method, initial_value):
    # We have to encode the type upfront, otherwise brownie incorrectly left-pads the
    # pool_type.
    pool_type = encode_abi(["bytes32"], [b"2CLP"])

    assert (
        getattr(mock_gyro_config, method)(mock_gyro_config.address, pool_type)
        == initial_value
    )

    pool_type_key = keccak(encode_abi(["bytes32", "bytes32"], [setting, b"2CLP"]))
    mock_gyro_config.setUint(pool_type_key, 7e18)
    assert (
        getattr(mock_gyro_config, method)(mock_gyro_config.address, pool_type) == 7e18
    )

    pool_key = keccak(
        encode_abi(["bytes32", "address"], [setting, mock_gyro_config.address])
    )
    mock_gyro_config.setUint(pool_key, 5e18)
    assert (
        getattr(mock_gyro_config, method)(mock_gyro_config.address, pool_type) == 5e18
    )


@pytest.mark.parametrize(
    "setting,method",
    (
        (b"PROTOCOL_SWAP_FEE_PERC", "getSwapFeePercForPool"),
        (b"PROTOCOL_FEE_GYRO_PORTION", "getProtocolFeeGyroPortionForPool"),
    ),
)
def test_treats_0_as_settable_value(mock_gyro_config, setting, method):
    # We have to encode the type upfront, otherwise brownie incorrectly left-pads the
    # pool_type.
    pool_type = encode_abi(["bytes32"], [b"2CLP"])

    pool_type_key = keccak(encode_abi(["bytes32", "bytes32"], [setting, b"2CLP"]))
    mock_gyro_config.setUint(pool_type_key, 7e18)
    assert (
        getattr(mock_gyro_config, method)(mock_gyro_config.address, pool_type) == 7e18
    )

    pool_key = keccak(
        encode_abi(["bytes32", "address"], [setting, mock_gyro_config.address])
    )
    mock_gyro_config.setUint(pool_key, 0)
    assert getattr(mock_gyro_config, method)(mock_gyro_config.address, pool_type) == 0
