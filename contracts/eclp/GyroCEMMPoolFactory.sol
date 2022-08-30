// SPDX-License-Identifier: GPL-3.0-or-later
// This program is free software: you can redistribute it and/or modify
// it under the terms of the GNU General Public License as published by
// the Free Software Foundation, either version 3 of the License, or
// (at your option) any later version.

// This program is distributed in the hope that it will be useful,
// but WITHOUT ANY WARRANTY; without even the implied warranty of
// MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
// GNU General Public License for more details.

// You should have received a copy of the GNU General Public License
// along with this program.  If not, see <http://www.gnu.org/licenses/>.

pragma solidity 0.7.6;
pragma experimental ABIEncoderV2;

import "@balancer-labs/v2-vault/contracts/interfaces/IVault.sol";

import "@balancer-labs/v2-pool-utils/contracts/factories/BasePoolSplitCodeFactory.sol";
import "@balancer-labs/v2-pool-utils/contracts/factories/FactoryWidePauseWindow.sol";

import "../../interfaces/IGyroCEMMPoolFactory.sol";
import "../../interfaces/ICappedLiquidity.sol";
import "./GyroCEMMPool.sol";

contract GyroCEMMPoolFactory is IGyroCEMMPoolFactory, BasePoolSplitCodeFactory, FactoryWidePauseWindow {
    address public immutable gyroConfigAddress;

    uint256 public constant PAUSE_WINDOW_DURATION = 90 days;
    uint256 public constant BUFFER_PERIOD_DURATION = 30 days;

    constructor(IVault vault, address _gyroConfigAddress) BasePoolSplitCodeFactory(vault, type(GyroCEMMPool).creationCode) {
        _grequire(_gyroConfigAddress != address(0), GyroErrors.ZERO_ADDRESS);
        _grequire(address(vault) != address(0), GyroErrors.ZERO_ADDRESS);
        gyroConfigAddress = _gyroConfigAddress;
    }

    /**
     * @dev Deploys a new `GyroCEMMPool`.
     */
    function create(
        string memory name,
        string memory symbol,
        IERC20[] memory tokens,
        GyroCEMMMath.Params memory cemmParams,
        GyroCEMMMath.DerivedParams memory derivedCemmParams,
        uint256 swapFeePercentage,
        bool oracleEnabled,
        address owner
    ) external override returns (address) {
        ExtensibleWeightedPool2Tokens.NewPoolParams memory baseParams = _makePoolParams(
            name,
            symbol,
            tokens,
            swapFeePercentage,
            oracleEnabled,
            owner
        );

        GyroCEMMPool.GyroParams memory params = GyroCEMMPool.GyroParams({
            baseParams: baseParams,
            cemmParams: cemmParams,
            derivedCemmParams: derivedCemmParams
        });

        return _create(abi.encode(params, gyroConfigAddress));
    }

    function _makePoolParams(
        string memory name,
        string memory symbol,
        IERC20[] memory tokens,
        uint256 swapFeePercentage,
        bool oracleEnabled,
        address owner
    ) internal view returns (ExtensibleWeightedPool2Tokens.NewPoolParams memory) {
        return
            ExtensibleWeightedPool2Tokens.NewPoolParams({
                vault: getVault(),
                name: name,
                symbol: symbol,
                token0: tokens[0],
                token1: tokens[1],
                swapFeePercentage: swapFeePercentage,
                pauseWindowDuration: PAUSE_WINDOW_DURATION,
                bufferPeriodDuration: BUFFER_PERIOD_DURATION,
                oracleEnabled: oracleEnabled,
                owner: owner
            });
    }
}
