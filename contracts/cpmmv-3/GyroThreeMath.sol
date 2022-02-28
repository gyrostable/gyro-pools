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

pragma solidity ^0.7.0;

import "@balancer-labs/v2-solidity-utils/contracts/math/FixedPoint.sol";
import "@balancer-labs/v2-solidity-utils/contracts/math/Math.sol";
import "@balancer-labs/v2-solidity-utils/contracts/helpers/InputHelpers.sol";

import "./GyroThreePoolErrors.sol";

// These functions start with an underscore, as if they were part of a contract and not a library. At some point this
// should be fixed.
// solhint-disable private-vars-leading-underscore

library GyroThreeMath {
    using FixedPoint for uint256;

    // Swap limits: amounts swapped may not be larger than this percentage of total balance.
    // _MAX_OUT_RATIO also ensures that we never compute swaps that take more out than is in the pool. (because
    // it's <= ONE)
    uint256 internal constant _MAX_IN_RATIO = 0.3e18;
    uint256 internal constant _MAX_OUT_RATIO = 0.3e18;
    uint256 internal constant _MIN_BAL_RATIO = 1e13; // 1e-5

    // Stopping criterion for the Newton iteration that computes the invariant:
    // - Stop if the step width doesn't shrink anymore by at least a factor _INVARIANT_SHRINKING_FACTOR_PER_STEP.
    // - ... but in any case, make at least _INVARIANT_MIN_ITERATIONS iterations. This is useful to compensate for a
    // less-than-ideal starting point, which is important when alpha is small.
    uint8 internal constant _INVARIANT_SHRINKING_FACTOR_PER_STEP = 10;
    uint8 internal constant _INVARIANT_MIN_ITERATIONS = 2;

    // Invariant is used to collect protocol swap fees by comparing its value between two times.
    // So we can round always to the same direction. It is also used to initiate the BPT amount
    // and, because there is a minimum BPT, we round down the invariant.
    // Argument root3Alpha = cube root of the lower price bound (symmetric across assets)
    // Note: all price bounds for the pool are alpha and 1/alpha
    function _calculateInvariant(uint256[] memory balances, uint256 root3Alpha) internal pure returns (uint256) {
        /**********************************************************************************************
        // Calculate root of cubic:
        // (1-alpha)L^3 - (x+y+z) * alpha^(2/3) * L^2 - (x*y + y*z + x*z) * alpha^(1/3) * L - x*y*z = 0
        // These coefficients are a,b,c,d respectively
        // here, a > 0, b < 0, c < 0, and d < 0
        // taking mb = -b and mc = -c
        /**********************************************************************************************/
        (uint256 a, uint256 mb, uint256 mc, uint256 md) = _calculateCubicTerms(balances, root3Alpha);
        return _calculateCubic(a, mb, mc, md);
    }

    /** @dev Prepares quadratic terms for input to _calculateCubic
     *  assumes a > 0, b < 0, c <= 0, and d <= 0 and returns a, -b, -c, -d
     *  terms come from cubic in Section 3.1.1
     *  argument root3Alpha = cube root of alpha
     */
    function _calculateCubicTerms(uint256[] memory balances, uint256 root3Alpha)
        internal
        pure
        returns (
            uint256 a,
            uint256 mb,
            uint256 mc,
            uint256 md
        )
    {
        uint256 alpha23 = root3Alpha.mulDown(root3Alpha); // alpha to the power of (2/3)
        uint256 alpha = alpha23.mulDown(root3Alpha);
        a = FixedPoint.ONE.sub(alpha);
        uint256 bterm = balances[0].add(balances[1]).add(balances[2]);
        mb = bterm.mulDown(alpha23);
        uint256 cterm = (balances[0].mulDown(balances[1])).add(balances[1].mulDown(balances[2])).add(balances[2].mulDown(balances[0]));
        mc = cterm.mulDown(root3Alpha);
        // TODO MAYBE to reduce rounding error amplification, multiply the smallest value last. Quite some effort though.
        md = balances[0].mulDown(balances[1]).mulDown(balances[2]);
    }

    /** @dev Calculate the maximal root of the polynomial a L^3 - mb L^2 - mc L - md.
     *   This root is always non-negative, and it is the unique positive root unless mb == mc == md == 0. */
    function _calculateCubic(
        uint256 a,
        uint256 mb,
        uint256 mc,
        uint256 md
    ) internal pure returns (uint256 rootEst) {
        if (md == 0) {
            // lower-order special case
            uint256 radic = mb.mulDown(mb).add(4 * a.mulDown(mc));
            rootEst = mb.add(radic.powDown(FixedPoint.ONE / 2)).divDown(2 * a);
        } else {
            rootEst = _calculateCubicStartingPoint(a, mb, mc, md);
            rootEst = _runNewtonIteration(a, mb, mc, md, rootEst);
        }
    }

    /** @dev Starting point for Newton iteration. Safe with all cubic polynomials where the coefficients have the appropriate
     *   signs, but calibrated to the particular polynomial for computing the invariant. */
    function _calculateCubicStartingPoint(
        uint256 a,
        uint256 mb,
        uint256 mc,
        uint256 // md
    ) internal pure returns (uint256 l0) {
        uint256 radic = mb.mulUp(mb).add(a.mulUp(mc).mulUp(3 * FixedPoint.ONE));
        uint256 lmin = mb.divUp(a * 3).add(radic.powUp(FixedPoint.ONE / 2).divUp(a * 3));
        // The factor 3/2 is a magic number found experimentally for our invariant. All factors > 1 are safe.
        l0 = lmin.mulUp((3 * FixedPoint.ONE) / 2);
    }

    /** @dev Find a root of the given polynomial with the given starting point l.
     *   Safe iff l > the local minimum.
     *   Note that f(l) may be negative for the first iteration and will then be positive (up to rounding errors).
     *   f'(l) is always positive for the range of values we consider.
     *   See write-up, Appendix A. */
    function _runNewtonIteration(
        uint256 a,
        uint256 mb,
        uint256 mc,
        uint256 md,
        uint256 rootEst
    ) internal pure returns (uint256) {
        uint256 deltaAbsPrev = 0;
        for (uint256 iteration = 0; iteration < 255; ++iteration) {
            // The delta to the next step can be positive or negative, so we represent a positive and a negative part
            // separately. The signed delta is delta_plus - delta_minus, but we only ever consider its absolute value.
            (uint256 deltaAbs, bool deltaIsPos) = _calcNewtonDelta(a, mb, mc, md, rootEst);
            // ^ Note: If we ever set _INVARIANT_MIN_ITERATIONS=0, the following should include `iteration >= 1`.
            if (deltaAbs == 0 || (iteration >= _INVARIANT_MIN_ITERATIONS && deltaIsPos))
                // Iteration literally stopped or numerical error dominates
                return rootEst;
            if (iteration >= _INVARIANT_MIN_ITERATIONS && deltaAbs >= deltaAbsPrev / _INVARIANT_SHRINKING_FACTOR_PER_STEP) {
                // stalled
                // Move one more step to the left to ensure we're underestimating, rather than overestimating, L
                return rootEst - deltaAbs;
            }
            deltaAbsPrev = deltaAbs;
            if (deltaIsPos) rootEst = rootEst.add(deltaAbs);
            else rootEst = rootEst.sub(deltaAbs);
        }
        _revert(GyroThreePoolErrors.INVARIANT_DIDNT_CONVERGE);
    }

    // -f(l)/f'(l), represented as an absolute value and a sign. Require that l is sufficiently large so that f is strictly increasing.
    function _calcNewtonDelta(
        uint256 a,
        uint256 mb,
        uint256 mc,
        uint256 md,
        uint256 rootEst
    ) internal pure returns (uint256 deltaAbs, bool deltaIsPos) {
        // We aim to, when in doubt, overestimate the step in the negative direction and in absolute value.
        // Subtraction does not underflow since rootEst is chosen so that it's always above the (only) local minimum.
        uint256 dfRootEst = rootEst.mulDown(rootEst).mulDown(3 * a).sub(rootEst.mulUp(2 * mb)).sub(mc);
        // Note: We know that a rootEst^2 / dfRootEst ~ 1. (see the Mathematica notebook).
        uint256 deltaMinus = rootEst.mulUp(rootEst).mulUp(rootEst);
        deltaMinus = deltaMinus.mulUp(a).divUp(dfRootEst);

        uint256 deltaPlus = rootEst.mulDown(rootEst).mulDown(mb);
        deltaPlus = deltaPlus.add(rootEst.mulDown(mc)).divDown(dfRootEst);
        deltaPlus = deltaPlus.add(md.divDown(dfRootEst));

        deltaIsPos = (deltaPlus >= deltaMinus);
        deltaAbs = (deltaIsPos ? deltaPlus - deltaMinus : deltaMinus - deltaPlus);
    }

    /** @dev Computes how many tokens can be taken out of a pool if `amountIn` are sent, given the
     * current balances and weights.
     * Changed signs compared to original algorithm to account for amountOut < 0.
     * See Proposition 12 in 3.1.4.*/
    function _calcOutGivenIn(
        uint256 balanceIn,
        uint256 balanceOut,
        uint256 amountIn,
        uint256 virtualOffsetInOut
    ) internal pure returns (uint256 amountOut) {
        /**********************************************************************************************
        // Described for X = `in' asset and Z = `out' asset, but equivalent for the other case       //
        // dX = incrX  = amountIn  > 0                                                               //
        // dZ = incrZ = amountOut < 0                                                                //
        // x = balanceIn             x' = x +  virtualOffset                                         //
        // z = balanceOut            z' = z +  virtualOffset                                         //
        // L  = inv.Liq                   /            x' * z'          \                            //
        //                   |dZ| = z' - |   --------------------------  |                           //
        //  x' = virtIn                   \          ( x' + dX)         /                            //
        //  z' = virtOut                                                                             //
        // Note that -dz > 0 is what the trader receives.                                            //
        // We exploit the fact that this formula is symmetric up to virtualParam{X,Y,Z}.             //
        **********************************************************************************************/
        _require(amountIn <= balanceIn.mulDown(_MAX_IN_RATIO), Errors.MAX_IN_RATIO);

        {
            uint256 virtIn = balanceIn.add(virtualOffsetInOut);
            uint256 virtOut = balanceOut.add(virtualOffsetInOut);
            uint256 denominator = virtIn.add(amountIn);
            uint256 subtrahend = virtIn.mulUp(virtOut).divUp(denominator);
            amountOut = virtOut.sub(subtrahend);
        }

        _require(amountOut < balanceOut, GyroThreePoolErrors.ASSET_BOUNDS_EXCEEDED);
        (uint256 balOutNew, uint256 balInNew) = (balanceOut.sub(amountOut), balanceIn.add(amountIn));

        if (balOutNew >= balInNew) {
            _require(balInNew.divDown(balOutNew) > _MIN_BAL_RATIO, GyroThreePoolErrors.ASSET_BOUNDS_EXCEEDED);
        } else {
            _require(balOutNew.divDown(balInNew) > _MIN_BAL_RATIO, GyroThreePoolErrors.ASSET_BOUNDS_EXCEEDED);
        }

        // Note that this in particular reverts if amountOut > balanceOut, i.e., if the out-amount would be more than
        // the balance.
        _require(amountOut <= balanceOut.mulDown(_MAX_OUT_RATIO), Errors.MAX_OUT_RATIO);
    }

    /** @dev Computes how many tokens must be sent to a pool in order to take `amountOut`, given the
     * currhent balances and weights.
     * Similar to the one before but adapting bc negative values (amountOut would be negative).*/
    function _calcInGivenOut(
        uint256 balanceIn,
        uint256 balanceOut,
        uint256 amountOut,
        uint256 virtualOffsetInOut
    ) internal pure returns (uint256 amountIn) {
        /**********************************************************************************************
        // Described for X = `in' asset and Z = `out' asset, but equivalent for the other case       //
        // dX = incrX  = amountIn  > 0                                                               //
        // dZ = incrZ = amountOut < 0                                                                //
        // x = balanceIn             x' = x +  virtualOffset                                         //
        // z = balanceOut            z' = z +  virtualOffset                                         //
        // L  = inv.Liq            /            x' * z'          \                                   //
        //                   dX = |   --------------------------  | - x'                             //
        //  x' = virtIn            \          ( z' + dZ)         /                                   //
        //  z' = virtOut                                                                             //
        // Note that dz < 0 < dx.                                                                    //
        // We exploit the fact that this formula is symmetric up to virtualParam{X,Y,Z}.             //
        **********************************************************************************************/

        // Note that this in particular reverts if amountOut > balanceOut, i.e., if the trader tries to take more out of
        // the pool than is in it.
        _require(amountOut <= balanceOut.mulDown(_MAX_OUT_RATIO), Errors.MAX_OUT_RATIO);

        {
            uint256 virtIn = balanceIn.add(virtualOffsetInOut);
            uint256 virtOut = balanceOut.add(virtualOffsetInOut);
            uint256 denominator = virtOut.sub(amountOut);
            uint256 minuend = virtIn.mulUp(virtOut).divUp(denominator);
            amountIn = minuend.sub(virtIn);
        }

        (uint256 balOutNew, uint256 balInNew) = (balanceOut.sub(amountOut), balanceIn.add(amountIn));

        if (balOutNew >= balInNew) {
            _require(balInNew.divDown(balOutNew) > _MIN_BAL_RATIO, GyroThreePoolErrors.ASSET_BOUNDS_EXCEEDED);
        } else {
            _require(balOutNew.divDown(balInNew) > _MIN_BAL_RATIO, GyroThreePoolErrors.ASSET_BOUNDS_EXCEEDED);
        }

        _require(amountIn <= balanceIn.mulDown(_MAX_IN_RATIO), Errors.MAX_IN_RATIO);
    }
}
