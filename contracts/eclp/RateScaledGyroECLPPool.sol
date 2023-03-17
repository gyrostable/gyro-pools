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

    // TODO below to be moved to a separate base contract once I figured out diamond inheritance :/

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

    function _rateUnscalePrice(uint256 spotPrice) internal view override returns (uint256) {
        if (address(rateProvider0) != address(0)) spotPrice = spotPrice.mulDown(rateProvider0.getRate());
        if (address(rateProvider1) != address(0)) spotPrice = spotPrice.divDown(rateProvider1.getRate());
        return spotPrice;
    }

    // DEBUG / TESTING
    function getRawScalingFactors() external view returns (uint256[] memory factors) {
        factors = new uint256[](2);
        factors[0] = _scalingFactor0;
        factors[1] = _scalingFactor1;
    }

    function getScalingFactors() external view returns (uint256[] memory factors) {
        factors = new uint256[](2);
        factors[0] = _scalingFactor(true);
        factors[1] = _scalingFactor(false);
    }
}
