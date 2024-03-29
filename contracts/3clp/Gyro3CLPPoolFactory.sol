// SPDX-License-Identifier: LicenseRef-Gyro-1.0
// for information on licensing please see the README in the GitHub repository <https://github.com/gyrostable/concentrated-lps>.

pragma solidity 0.7.6;
pragma experimental ABIEncoderV2;

import "@balancer-labs/v2-vault/contracts/interfaces/IVault.sol";

import "@balancer-labs/v2-pool-utils/contracts/factories/BasePoolSplitCodeFactory.sol";

import "../../interfaces/ICappedLiquidity.sol";
import "../../interfaces/IGyro3CLPPoolFactory.sol";

import "./Gyro3CLPPool.sol";

contract Gyro3CLPPoolFactory is IGyro3CLPPoolFactory, BasePoolSplitCodeFactory {
    address public immutable gyroConfigAddress;

    constructor(IVault vault, address _gyroConfigAddress) BasePoolSplitCodeFactory(vault, type(Gyro3CLPPool).creationCode) {
        gyroConfigAddress = _gyroConfigAddress;
    }

    /**
     * @dev Deploys a new `Gyro3CLPPool`.
     */
    function create(Gyro3CLPPool.NewPoolConfigParams memory config) external override returns (address) {
        Gyro3CLPPool.NewPoolParams memory params = Gyro3CLPPool.NewPoolParams({vault: getVault(), configAddress: gyroConfigAddress, config: config});

        return _create(abi.encode(params));
    }
}
