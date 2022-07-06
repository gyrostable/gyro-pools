// SPDX-License-Identifier: GPL-3.0-or-later
pragma solidity ^0.7.0;
pragma experimental ABIEncoderV2;

import "@balancer-labs/v2-solidity-utils/contracts/math/FixedPoint.sol";

import "../interfaces/ICappedLiquidity.sol";

contract CappedLiquidity is ICappedLiquidity {
    using FixedPoint for uint256;

    string internal constant _OVER_CAP = "over liquidity cap";

    CapParams internal _capParams;

    constructor(CapParams memory params) {
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
        require(amountMinted.add(userBalance) <= params.perAddressCap, _OVER_CAP);
        require(amountMinted.add(currentSupply) <= params.globalCap, _OVER_CAP);
    }

    function capEnabled() external view override returns (bool) {
        return _capParams.capEnabled;
    }

    function perAddressCap() external view override returns (uint256) {
        return _capParams.perAddressCap;
    }

    function globalCap() external view override returns (uint256) {
        return _capParams.globalCap;
    }
}
