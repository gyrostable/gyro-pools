pragma solidity ^0.7.6;
pragma experimental ABIEncoderV2;

import "./GyroECLPPool.sol";
import "@balancer-labs/v2-pool-utils/contracts/interfaces/IRateProvider.sol";

import "../../libraries/GyroFixedPoint.sol";

/// @notice Extension of GyroECLPPool where one or both assets can be scaled by a rate provider.
/// @dev NOTE that we do not implement caching for rates, so this is inefficient when getting rates is expensive.
contract RateScaledGyroECLPPool is GyroECLPPool {
    constructor(
        GyroParams memory params,
        address configAddress,
        address rateProvider0_,
        address rateProvider1_
    ) GyroECLPPool(params, configAddress) {
        rateProvider0 = IRateProvider(rateProvider0_);
        rateProvider1 = IRateProvider(rateProvider1_);
    }

    // The below code is general and can be used to add rate scaling to any child of ExtensibleWeightedPool2Tokens.
    // We don't have it as a base class because of Solidity's limitations with multiple inheritance.

    using GyroFixedPoint for uint256;
    using SafeCast for uint256;

    IRateProvider public immutable rateProvider0;
    IRateProvider public immutable rateProvider1;

    function _scalingFactor(bool token0) internal view override returns (uint256) {
        IRateProvider rateProvider;
        uint256 scalingFactor;
        if (token0) {
            rateProvider = rateProvider0;
            scalingFactor = _scalingFactor0;
        } else {
            rateProvider = rateProvider1;
            scalingFactor = _scalingFactor1;
        }
        if (address(rateProvider) != address(0)) scalingFactor = scalingFactor.mulDown(rateProvider.getRate());
        return scalingFactor;
    }

    function _adjustPrice(uint256 spotPrice) internal view override returns (uint256) {
        if (address(rateProvider0) != address(0)) spotPrice = spotPrice.mulDown(rateProvider0.getRate());
        if (address(rateProvider1) != address(0)) spotPrice = spotPrice.divDown(rateProvider1.getRate());
        return spotPrice;
    }
}
