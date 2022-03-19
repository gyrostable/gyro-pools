// SPDX-License-Identifier: GPL-3.0-or-later

pragma solidity ^0.7.0;
pragma experimental ABIEncoderV2;

import "../GyroCEMMMath.sol";
import "../../../libraries/GyroPoolMath.sol";

contract GyroCEMMMathTesting {
    function validateParams(GyroCEMMMath.Params memory params) external pure {
        return GyroCEMMMath.validateParams(params);
    }

    function validateDerivedParams(GyroCEMMMath.Params memory params, GyroCEMMMath.DerivedParams memory derived) external pure {
        GyroCEMMMath.validateDerivedParams(params, derived);
    }

    function scalarProd(GyroCEMMMath.Vector2 memory t1, GyroCEMMMath.Vector2 memory t2) external pure returns (int256 ret) {
        ret = GyroCEMMMath.scalarProd(t1, t2);
    }

    function mulA(GyroCEMMMath.Params memory params, GyroCEMMMath.Vector2 memory tp) external pure returns (GyroCEMMMath.Vector2 memory t) {
        t = GyroCEMMMath.mulA(params, tp);
    }

    function zeta(GyroCEMMMath.Params memory params, int256 px) external pure returns (int256 pxc) {
        pxc = GyroCEMMMath.zeta(params, px);
    }

    function tau(GyroCEMMMath.Params memory params, int256 px) external pure returns (GyroCEMMMath.Vector2 memory tpp) {
        tpp = GyroCEMMMath.tau(params, px);
    }

    function tau(
        GyroCEMMMath.Params memory params,
        int256 px,
        int256 sqrt
    ) external pure returns (GyroCEMMMath.Vector2 memory tpp) {
        return GyroCEMMMath.tau(params, px, sqrt);
    }

    function mkDerivedParams(GyroCEMMMath.Params memory params) external pure returns (GyroCEMMMath.DerivedParams memory derived) {
        derived = GyroCEMMMath.mkDerivedParams(params);
    }

    function eta(int256 pxc) external pure returns (GyroCEMMMath.Vector2 memory tpp) {
        tpp = GyroCEMMMath.eta(pxc);
    }

    function eta(int256 pxc, int256 z) external pure returns (GyroCEMMMath.Vector2 memory tpp) {
        tpp = GyroCEMMMath.eta(pxc, z);
    }

    function virtualOffset0(
        GyroCEMMMath.Params memory params,
        GyroCEMMMath.DerivedParams memory derived,
        GyroCEMMMath.Vector2 memory r
    ) external pure returns (int256) {
        return GyroCEMMMath.virtualOffset0(params, derived, r);
    }

    function virtualOffset1(
        GyroCEMMMath.Params memory params,
        GyroCEMMMath.DerivedParams memory derived,
        GyroCEMMMath.Vector2 memory r
    ) external pure returns (int256) {
        return GyroCEMMMath.virtualOffset1(params, derived, r);
    }

    function maxBalances0(
        GyroCEMMMath.Params memory params,
        GyroCEMMMath.DerivedParams memory derived,
        int256 invariant
    ) external pure returns (int256) {
        return GyroCEMMMath.maxBalances0(params, derived, invariant);
    }

    function maxBalances1(
        GyroCEMMMath.Params memory params,
        GyroCEMMMath.DerivedParams memory derived,
        int256 invariant
    ) external pure returns (int256) {
        return GyroCEMMMath.maxBalances1(params, derived, invariant);
    }

    function calculateInvariant(
        uint256[] memory balances,
        GyroCEMMMath.Params memory params,
        GyroCEMMMath.DerivedParams memory derived
    ) external pure returns (uint256 uinvariant) {
        uinvariant = GyroCEMMMath.calculateInvariant(balances, params, derived);
    }

    function calculatePrice(
        uint256[] memory balances,
        GyroCEMMMath.Params memory params,
        GyroCEMMMath.DerivedParams memory derived,
        int256 invariant
    ) external pure returns (uint256 px) {
        px = GyroCEMMMath.calculatePrice(balances, params, derived, invariant);
    }

    function checkAssetBounds(
        GyroCEMMMath.Params memory params,
        GyroCEMMMath.DerivedParams memory derived,
        int256 invariant,
        int256 newBalance,
        uint8 assetIndex
    ) external pure {
        GyroCEMMMath.checkAssetBounds(params, derived, invariant, newBalance, assetIndex);
    }

    function calcOutGivenIn(
        uint256[] memory balances,
        uint256 amountIn,
        bool tokenInIsToken0,
        GyroCEMMMath.Params memory params,
        GyroCEMMMath.DerivedParams memory derived,
        uint256 uinvariant
    ) external pure returns (uint256 amountOut) {
        amountOut = GyroCEMMMath.calcOutGivenIn(balances, amountIn, tokenInIsToken0, params, derived, uinvariant);
    }

    function calcInGivenOut(
        uint256[] memory balances,
        uint256 amountOut,
        bool tokenInIsToken0,
        GyroCEMMMath.Params memory params,
        GyroCEMMMath.DerivedParams memory derived,
        uint256 uinvariant
    ) external pure returns (uint256 amountIn) {
        amountIn = GyroCEMMMath.calcInGivenOut(balances, amountOut, tokenInIsToken0, params, derived, uinvariant);
    }

    function calcYGivenX(
        int256 x,
        GyroCEMMMath.Params memory params,
        GyroCEMMMath.DerivedParams memory derived,
        int256 invariant
    ) external pure returns (int256 y) {
        y = GyroCEMMMath.calcYGivenX(x, params, derived, invariant);
    }

    function calcXGivenY(
        int256 y,
        GyroCEMMMath.Params memory params,
        GyroCEMMMath.DerivedParams memory derived,
        int256 invariant
    ) external pure returns (int256 x) {
        x = GyroCEMMMath.calcXGivenY(y, params, derived, invariant);
    }

    function calcAtAChi(
        int256 x,
        int256 y,
        GyroCEMMMath.Params memory p,
        GyroCEMMMath.DerivedParams memory d
    ) external pure returns (int256) {
        return GyroCEMMMath.calcAtAChi(x, y, p, d);
    }

    function calcAChiAChi(GyroCEMMMath.Params memory p, GyroCEMMMath.DerivedParams memory d) external pure returns (int256) {
        return GyroCEMMMath.calcAChiAChi(p, d);
    }

    function calcMinAtxAChiySqPlusAtxSq(
        int256 x,
        int256 y,
        GyroCEMMMath.Params memory p,
        GyroCEMMMath.DerivedParams memory d
    ) external pure returns (int256) {
        return GyroCEMMMath.calcMinAtxAChiySqPlusAtxSq(x, y, p, d);
    }

    function calc2AtxAtyAChixAChiy(
        int256 x,
        int256 y,
        GyroCEMMMath.Params memory p,
        GyroCEMMMath.DerivedParams memory d
    ) external pure returns (int256) {
        return GyroCEMMMath.calc2AtxAtyAChixAChiy(x, y, p, d);
    }

    function calcMinAtyAChixSqPlusAtySq(
        int256 x,
        int256 y,
        GyroCEMMMath.Params memory p,
        GyroCEMMMath.DerivedParams memory d
    ) external pure returns (int256) {
        return GyroCEMMMath.calcMinAtyAChixSqPlusAtySq(x, y, p, d);
    }

    function calcInvariantSqrt(
        int256 x,
        int256 y,
        GyroCEMMMath.Params memory p,
        GyroCEMMMath.DerivedParams memory d
    ) external pure returns (int256) {
        return GyroCEMMMath.calcInvariantSqrt(x, y, p, d);
    }

    function solveQuadraticSwap(
        int256 lambda,
        int256 x,
        int256 s,
        int256 c,
        GyroCEMMMath.Vector2 memory r,
        GyroCEMMMath.Vector2 memory ab,
        GyroCEMMMath.Vector2 memory tauBeta
    ) external pure returns (int256) {
        return GyroCEMMMath.solveQuadraticSwap(lambda, x, s, c, r, ab, tauBeta);
    }

    function calcXpXpDivLambdaLambda(
        int256 x,
        GyroCEMMMath.Vector2 memory r,
        int256 lambda,
        int256 s,
        int256 c,
        GyroCEMMMath.Vector2 memory tauBeta
    ) external pure returns (int256) {
        return GyroCEMMMath.calcXpXpDivLambdaLambda(x, r, lambda, s, c, tauBeta);
    }

    function liquidityInvariantUpdate(
        uint256[] memory balances,
        uint256 uinvariant,
        uint256[] memory deltaBalances,
        bool isIncreaseLiq
    ) external pure returns (uint256 unewInvariant) {
        unewInvariant = GyroPoolMath.liquidityInvariantUpdate(balances, uinvariant, deltaBalances, isIncreaseLiq);
    }

    function _calcAllTokensInGivenExactBptOut(
        uint256[] memory balances,
        uint256 bptAmountOut,
        uint256 totalBPT
    ) external pure returns (uint256[] memory) {
        return GyroPoolMath._calcAllTokensInGivenExactBptOut(balances, bptAmountOut, totalBPT);
    }

    function _calcTokensOutGivenExactBptIn(
        uint256[] memory balances,
        uint256 bptAmountIn,
        uint256 totalBPT
    ) external pure returns (uint256[] memory) {
        return GyroPoolMath._calcTokensOutGivenExactBptIn(balances, bptAmountIn, totalBPT);
    }

    function _calcProtocolFees(
        uint256 previousInvariant,
        uint256 currentInvariant,
        uint256 currentBptSupply,
        uint256 protocolSwapFeePerc,
        uint256 protocolFeeGyroPortion
    ) external pure returns (uint256, uint256) {
        return GyroPoolMath._calcProtocolFees(previousInvariant, currentInvariant, currentBptSupply, protocolSwapFeePerc, protocolFeeGyroPortion);
    }
}
