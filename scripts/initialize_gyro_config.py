from brownie import interface, chain, ZERO_ADDRESS, accounts
from scripts.constants import GYROSCOPE_ADDRESSES
from scripts.utils import format_to_bytes, get_deployer, make_tx_params


KEYS = [
    ("PROTOCOL_SWAP_FEE_PERC", 0),
    ("PROTOCOL_FEE_GYRO_PORTION", 0),
    ("GYRO_TREASURY", ZERO_ADDRESS),
    ("BAL_TREASURY", ZERO_ADDRESS),
]


def main():
    account = get_deployer()
    gyro_config = interface.IGyroConfig(GYROSCOPE_ADDRESSES[chain.id]["gyro_config"])
    keys = gyro_config.listKeys()
    for key, value in KEYS:
        formatted_key = format_to_bytes(key, 32, output_hex=True)
        if formatted_key in keys:
            continue
        method = "setUint" if isinstance(value, int) else "setAddress"
        getattr(gyro_config, method)(
            formatted_key, value, {"from": get_deployer(), **make_tx_params()}
        )
