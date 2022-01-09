
pragma solidity ^0.7.0;

/// @dev We can't call the functions of the math library for testing b/c they're internal. That's why this contract forwards calls to the math library.

import "../GyroThreeMath.sol";

contract GyroThreeMathTesting {
    function _calculateInvariant(uint256[] memory balances, uint256 root3Alpha)
        public
        pure
        returns (uint256) {
        return GyroThreeMath._calculateInvariant(balances, root3Alpha);
    }
    function _calculateCubicTerms(uint256[] memory balances, uint256 root3Alpha)
        public
        pure
        returns (
            uint256 a,
            uint256 mb,
            uint256 mc,
            uint256 md
        ) {
        return GyroThreeMath._calculateCubicTerms(balances, root3Alpha);
    }
    function _calculateCubic(
        uint256 a,
        uint256 mb,
        uint256 mc,
        uint256 md
    ) public pure returns (uint256 l) {
        return GyroThreeMath._calculateCubic(a, mb, mc, md);
    }
    function _calculateCubicStartingPoint(uint256 a, uint256 mb, uint256 mc, uint256 md) public pure returns (uint256 l0) {
        return GyroThreeMath._calculateCubicStartingPoint(a, mb, mc, md);
    }
    function _runNewtonIteration (uint256 a, uint256 mb, uint256 mc, uint256 md, uint256 l)
            pure public returns (uint256) {
        return GyroThreeMath._runNewtonIteration(a, mb, mc, md, l);
    }
    function _calcNewtonDelta(uint256 a, uint256 mb, uint256 mc, uint256 md, uint256 l)
            pure public returns (uint256 delta_abs, bool delta_is_pos) {
        return GyroThreeMath._calcNewtonDelta(a, mb, mc, md, l);
    }
    function _liquidityInvariantUpdate(
        uint256[] memory lastBalances,
        uint256 root3Alpha,
        uint256 lastInvariant,
        uint256 incrZ,
        bool isIncreaseLiq
    ) public pure returns (uint256 invariant) {
        return GyroThreeMath._liquidityInvariantUpdate(lastBalances, root3Alpha, lastInvariant, incrZ, isIncreaseLiq);
    }
    function _calcOutGivenIn(
        uint256 balanceIn,
        uint256 balanceOut,
        uint256 amountIn,
        uint256 virtualOffsetInOut
    ) public pure returns (uint256 amountOut) {
        return GyroThreeMath._calcOutGivenIn(balanceIn, balanceOut, amountIn, virtualOffsetInOut);
    }
    function _calcInGivenOut(
        uint256 balanceIn,
        uint256 balanceOut,
        uint256 amountOut,
        uint256 virtualOffsetInOut
    ) public pure returns (uint256 amountIn) {
        return GyroThreeMath._calcInGivenOut(balanceIn, balanceOut, amountOut, virtualOffsetInOut);
    }
    function _calcAllTokensInGivenExactBptOut(
        uint256[] memory balances,
        uint256 bptAmountOut,
        uint256 totalBPT
    ) public pure returns (uint256[] memory) {
        return GyroThreeMath._calcAllTokensInGivenExactBptOut(balances, bptAmountOut, totalBPT);
    }
    function _calcTokensOutGivenExactBptIn(
        uint256[] memory balances,
        uint256 bptAmountIn,
        uint256 totalBPT
    ) public pure returns (uint256[] memory) {
        return GyroThreeMath._calcTokensOutGivenExactBptIn(balances, bptAmountIn, totalBPT);
    }
    function _calculateCbrtPrice(
        uint256 invariant,
        uint256 virtualX,
        uint256 virtualY
    ) public pure returns (uint256) {
        return GyroThreeMath._calculateCbrtPrice(invariant, virtualX, virtualY);
    }
    function _calcProtocolFees(
        uint256 previousInvariant,
        uint256 currentInvariant,
        uint256 currentBptSupply,
        uint256 protocolSwapFeePerc,
        uint256 protocolFeeGyroPortion
    ) public pure returns (uint256, uint256) {
        return GyroThreeMath._calcProtocolFees(previousInvariant, currentInvariant, currentBptSupply,
                                               protocolSwapFeePerc, protocolFeeGyroPortion);
    }
}
