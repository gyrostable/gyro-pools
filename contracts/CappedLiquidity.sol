// SPDX-License-Identifier: GPL-3.0-or-later
pragma solidity 0.7.6;
pragma experimental ABIEncoderV2;

// import "@balancer-labs/v2-solidity-utils/contracts/math/FixedPoint.sol";
import "../libraries/GyroFixedPoint.sol";

import "../interfaces/ICappedLiquidity.sol";

import "@balancer-labs/v2-solidity-utils/contracts/helpers/IAuthentication.sol";

abstract contract CappedLiquidity is ICappedLiquidity {
    using GyroFixedPoint for uint256;

    string internal constant _OVER_GLOBAL_CAP = "over global liquidity cap";
    string internal constant _OVER_ADDRESS_CAP = "over address liquidity cap";
    string internal constant _NOT_AUTHORIZED = "not authorized";
    string internal constant _UNCAPPED = "pool is uncapped";

    CapParams internal _capParams;

    address public override capManager;

    constructor(CapParams memory params) {
        capManager = msg.sender;
        _capParams.capEnabled = params.capEnabled;
        _capParams.perAddressCap = params.perAddressCap;
        _capParams.globalCap = params.globalCap;
    }

    function capParams() external view override returns (CapParams memory) {
        return _capParams;
    }

    function setCapParams(CapParams memory params) external override {
        require(msg.sender == capManager, _NOT_AUTHORIZED);
        require(_capParams.capEnabled, _UNCAPPED);

        _capParams.capEnabled = params.capEnabled;
        _capParams.perAddressCap = params.perAddressCap;
        _capParams.globalCap = params.globalCap;
    }

    function _ensureCap(
        uint256 amountMinted,
        uint256 userBalance,
        uint256 currentSupply
    ) internal view {
        CapParams memory params = _capParams;
        require(amountMinted.add(userBalance) <= params.perAddressCap, _OVER_ADDRESS_CAP);
        require(amountMinted.add(currentSupply) <= params.globalCap, _OVER_GLOBAL_CAP);
    }
}
