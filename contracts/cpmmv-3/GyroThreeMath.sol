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

// import "@balancer-labs/v2-solidity-utils/contracts/math/FixedPoint.sol";
import "@balancer-labs/v2-solidity-utils/contracts/math/Math.sol";
import "@balancer-labs/v2-solidity-utils/contracts/helpers/InputHelpers.sol";

import "./GyroThreePoolErrors.sol";

import "../../libraries/GyroFixedPoint.sol";
import "../../libraries/GyroPoolMath.sol";

// These functions start with an underscore, as if they were part of a contract and not a library. At some point this
// should be fixed.
// solhint-disable private-vars-leading-underscore

/** @dev Math routines for the "symmetric" CPMMv3, i.e., the price bounds are [alpha, 1/alpha] for all three asset
 * pairs. We pass the parameter root3Alpha = 3rd root of alpha. We don't need to compute root3Alpha; instead, we
 * take this as the fundamental parameter and compute alpha = root3Alpha^3 where needed.
 *
 * A large part of this code is concerned with computing the invariant L from the real reserves, via Newton's method.
 * can be rather large and we need it to high precision. We apply various techniques to prevent an accumulation of
 * errors.
 */
library GyroThreeMath {
    using GyroFixedPoint for uint256;
    using GyroPoolMath for uint256; // number._sqrt(tolerance)

    // Swap limits: amounts swapped may not be larger than this percentage of total balance.
    // _MAX_OUT_RATIO also ensures that we never compute swaps that take more out than is in the pool. (because
    // it's <= ONE)
    uint256 internal constant _MAX_IN_RATIO = 0.3e18;
    uint256 internal constant _MAX_OUT_RATIO = 0.3e18;

    // Stopping criterion for the Newton iteration that computes the invariant:
    // - Stop if the step width doesn't shrink anymore by at least a factor _INVARIANT_SHRINKING_FACTOR_PER_STEP.
    // - ... but in any case, make at least _INVARIANT_MIN_ITERATIONS iterations. This is useful to compensate for a
    // less-than-ideal starting point, which is important when alpha is small.
    uint8 internal constant _INVARIANT_SHRINKING_FACTOR_PER_STEP = 8;
    uint8 internal constant _INVARIANT_MIN_ITERATIONS = 5;

    uint256 internal constant _MAX_BALANCES = 1e29;  // 1e11 = 100 billion, scaled
    uint256 internal constant _MIN_ROOT_3_ALPHA = 0.15874010519681997e18;  // 3rd root of 0.004, scaled
    uint256 internal constant _MAX_ROOT_3_ALPHA = 0.9999666655554938e18;  // 3rd root of 0.9999, scaled
    // Threshold of l where the normal method of computing the newton step would overflow and we need a workaround.
    uint256 internal constant _L_THRESHOLD_SIMPLE_NUMERICS = 4.87e31;  // 4.87e13, scaled
    // Threshold of l above which overflows may occur in the Newton iteration. This is far above the theoretically
    // maximum possible (starting or solution) value of l, so it would only ever be reached due to some other bug in the
    // newton iteration.
    uint256 internal constant _L_MAX = 4.86e34;  // 4.86e16, scaled

    /** @dev The invariant L corresponding to the given balances and alpha. */
    function _calculateInvariant(uint256[] memory balances, uint256 root3Alpha) internal pure returns (uint256 rootEst) {
        _require(balances[0] <= _MAX_BALANCES, GyroThreePoolErrors.BALANCES_TOO_LARGE);
        _require(balances[1] <= _MAX_BALANCES, GyroThreePoolErrors.BALANCES_TOO_LARGE);
        _require(balances[2] <= _MAX_BALANCES, GyroThreePoolErrors.BALANCES_TOO_LARGE);
        (uint256 a, uint256 mb, uint256 mc, uint256 md) = _calculateCubicTerms(balances, root3Alpha);
        return _calculateCubic(a, mb, mc, md, root3Alpha);
    }

    /** @dev Prepares cubic coefficients for input to _calculateCubic.
     *  We will have a > 0, b < 0, c <= 0, and d <= 0 and return a, -b, -c, -d, all >= 0
     *  Terms come from cubic in Section 3.1.1.*/
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
        // Order of operations is chosen to minimize error amplification.
        a = GyroFixedPoint.ONE.sub(root3Alpha.mulDown(root3Alpha).mulDown(root3Alpha));
        uint256 bterm = balances[0].add(balances[1]).add(balances[2]);
        mb = bterm.mulDown(root3Alpha).mulDown(root3Alpha);
        uint256 cterm = (balances[0].mulDown(balances[1])).add(balances[1].mulDown(balances[2])).add(balances[2].mulDown(balances[0]));
        mc = cterm.mulDown(root3Alpha);
        md = balances[0].mulDown(balances[1]).mulDown(balances[2]);
    }

    /** @dev Calculate the maximal root of the polynomial a L^3 - mb L^2 - mc L - md.
     *  This root is always non-negative, and it is the unique positive root unless mb == mc == md == 0.
     *  This function and all following ones require that a = 1 - root3Alpha^3 like in _calculateCubicTerms(), i.e.,
     *  this *cannot* be used for *any* cubic equation. We do this because `a` carries an error and to be able to
     *  rearrange operations to reduce error accumulation.*/
    function _calculateCubic(
        uint256 a,
        uint256 mb,
        uint256 mc,
        uint256 md,
        uint256 root3Alpha
    ) internal pure returns (uint256 rootEst) {
        rootEst = _calculateCubicStartingPoint(a, mb, mc, md);
        rootEst = _runNewtonIteration(mb, mc, md, root3Alpha, rootEst);
    }

    /** @dev Starting point for Newton iteration. Safe with all cubic polynomials where the coefficients have the
     *  appropriate signs and a in [0, 1], but calibrated to the particular polynomial for computing the invariant. */
    function _calculateCubicStartingPoint(
        uint256 a,
        uint256 mb,
        uint256 mc,
        uint256 // md
    ) internal pure returns (uint256 l0) {
        uint256 radic = mb.mulUp(mb).add(a.mulUp(mc * 3));
        uint256 lmin = mb.add(radic._sqrt(5)).divUp(a * 3);
        // This formula has been found experimentally. It is exact for alpha -> 1, where the factor is 1.5. All
        // factors > 1 are safe. For small alpha values, it is more efficient to fallback to a larger factor.
        uint256 alpha = GyroFixedPoint.ONE.sub(a); // We know that a is in [0, 1].
        uint256 factor = alpha >= 0.5e18 ? 1.5e18 : 2e18;
        l0 = lmin.mulUp(factor);
    }

    /** @dev Find a root of the given polynomial with the given starting point l.
     *   Safe iff l > the local minimum.
     *   Note that f(l) may be negative for the first iteration and will then be positive (up to rounding errors).
     *   f'(l) is always positive for the range of values we consider.
     *   See write-up, Appendix A.*/
    function _runNewtonIteration(
        uint256 mb,
        uint256 mc,
        uint256 md,
        uint256 root3Alpha,
        uint256 rootEst
    ) internal pure returns (uint256) {
        uint256 deltaAbsPrev = 0;
        for (uint256 iteration = 0; iteration < 255; ++iteration) {
            // The delta to the next step can be positive or negative, and we represent its sign separately.
            (uint256 deltaAbs, bool deltaIsPos) = _calcNewtonDelta(mb, mc, md, root3Alpha, rootEst);

            // Note: If we ever set _INVARIANT_MIN_ITERATIONS=0, the following should include `iteration >= 1`.
            if (deltaAbs <= 1) return rootEst;
            if (iteration >= _INVARIANT_MIN_ITERATIONS && deltaIsPos)
                // This should mathematically never happen. Thus, the numerical error dominates at this point.
                return rootEst;
            if (iteration >= _INVARIANT_MIN_ITERATIONS && deltaAbs >= deltaAbsPrev / _INVARIANT_SHRINKING_FACTOR_PER_STEP) {
                // The iteration has stalled and isn't making significant progress anymore.
                return rootEst;
            }
            deltaAbsPrev = deltaAbs;
            // TODO leave overflow check in here
            if (deltaIsPos) rootEst = rootEst.add(deltaAbs);
            else rootEst = rootEst.sub(deltaAbs);
        }
        _revert(GyroThreePoolErrors.INVARIANT_DIDNT_CONVERGE);
    }

    /** @dev The Newton step -f(l)/f'(l), represented by its absolute value and its sign.
     * Requires that l is sufficiently large (right of the local minimum) so that f' > 0.*/
    function _calcNewtonDelta(
        uint256 mb,
        uint256 mc,
        uint256 md,
        uint256 root3Alpha,
        uint256 rootEst
    ) internal pure returns (uint256 deltaAbs, bool deltaIsPos) {
        _require(rootEst <= _L_MAX, GyroThreePoolErrors.INVARIANT_TOO_LARGE);

        uint256 rootEst2 = rootEst.mulDown(rootEst);

        // The following is equal to dfRootEst^3 * a but with an order of operations optimized for precision.
        // Subtraction does not underflow since rootEst is chosen so that it's always above the (only) local minimum.
        // TODO test if this changes the SOR; perhaps undo if there's a problem. (minor optimization)
        // uint256 dfRootEst = (rootEst * 3).mulDown(rootEst);
        uint256 dfRootEst = 3 * rootEst2;
        dfRootEst = dfRootEst.sub(dfRootEst.mulDown(root3Alpha).mulDown(root3Alpha).mulDown(root3Alpha));
        dfRootEst = dfRootEst.sub(Math.mul(2, rootEst.mulDown(mb))).sub(mc);

        // We distinguish two cases: Relatively small values of rootEst, where we can use simple operations, and larger
        // values, where the simple operations may overflow and we need to use functions that compensate for that.
        uint256 deltaMinus;
        uint256 deltaPlus;
        if (rootEst <= _L_THRESHOLD_SIMPLE_NUMERICS) {
            // Calculations are ordered and grouped to minimize rounding error amplification.
            deltaMinus = rootEst2.mulDown(rootEst);
            deltaMinus = deltaMinus.sub(deltaMinus.mulDown(root3Alpha).mulDown(root3Alpha).mulDown(root3Alpha));
            deltaMinus = deltaMinus.divDown(dfRootEst);

            // NB: We could order the operations here in much the same way we did above to reduce errors. But tests show
            // that this has no significant effect, and it would lead to more complex code.
            deltaPlus = rootEst2.mulDown(mb);
            deltaPlus = deltaPlus.add(rootEst.mulDown(mc)).divDown(dfRootEst);
            deltaPlus = deltaPlus.add(md.divDown(dfRootEst));
        } else {
            // Same operations as above, but we replace some of the operations with their variants that work for larger
            // numbers.
            deltaMinus = rootEst2.mulDownLargeSmall(rootEst);
            deltaMinus = deltaMinus.sub(deltaMinus.mulDownLargeSmall(root3Alpha).mulDownLargeSmall(root3Alpha)
                .mulDownLargeSmall(root3Alpha));
            // TODO add comment about why divDownLarge() doesn't crash and doesn't lose too much precision (dfRootEst >> 0)
            // TODO Leave the check in here? - OR add a check at the very top of this block (prob better)
            deltaMinus = deltaMinus.divDownLarge(dfRootEst);

            // We use mulDownLargeSmall() to prevent an overflow that can occur for large balances and alpha very
            // close to 1.
            deltaPlus = rootEst2.mulDownLargeSmall(mb);
            // We use mc.mulDownLargeSmall(rootEst), rather than the other way round, because mc is usually bigger.
            // TODO add comment about why divDownLarge() doesn't crash and doesn't lose too much precision (dfRootEst >> 0)
            // TODO I think the first mulDownLargeSmall can be just mulDown.
            deltaPlus = deltaPlus.add(mc.mulDownLargeSmall(rootEst)).divDownLarge(dfRootEst);
            deltaPlus = deltaPlus.add(md.divDown(dfRootEst));
        }

        deltaIsPos = (deltaPlus >= deltaMinus);
        deltaAbs = (deltaIsPos ? deltaPlus.sub(deltaMinus) : deltaMinus.sub(deltaPlus));
    }

    /** @dev Computes how many tokens can be taken out of a pool if `amountIn` are sent, given the current balances and
     * price bounds.
     * See Proposition 13 in 3.1.4. In contrast to the proposition, we use two separate functions for trading given the
     * out-amount and the in-amount, respectively.
     * The virtualOffset argument depends on the computed invariant. While the calculation is very precise, small errors
     * can occur. We add a very small margin to ensure that such errors are not to the detriment of the pool. */
    function _calcOutGivenIn(
        uint256 balanceIn,
        uint256 balanceOut,
        uint256 amountIn,
        uint256 virtualOffset
    ) internal pure returns (uint256 amountOut) {
        /**********************************************************************************************
        // Described for X = `in' asset and Z = `out' asset, but equivalent for the other case       //
        // dX = incrX  = amountIn  > 0                                                               //
        // dZ = incrZ = amountOut < 0                                                                //
        // x = balanceIn             x' = x +  virtualOffset                                         //
        // z = balanceOut            z' = z +  virtualOffset                                         //
        // L  = inv.Liq                   /            x' * z'          \          z' * dX           //
        //                   |dZ| = z' - |   --------------------------  |   = ---------------       //
        //  x' = virtIn                   \          ( x' + dX)         /          x' + dX           //
        //  z' = virtOut                                                                             //
        // Note that -dz > 0 is what the trader receives.                                            //
        // We exploit the fact that this formula is symmetric and does not depend on which asset is  //
        // which.
        // We assume that the virtualOffset carries a relative +/- 3e-18 error due to the invariant  //
        // calculation add an appropriate safety margin.                                             //
        **********************************************************************************************/
        _require(amountIn <= balanceIn.mulDown(_MAX_IN_RATIO), Errors.MAX_IN_RATIO);

        {
            // The factors in total lead to a multiplicative "safety margin" between the employed virtual offsets
            // very slightly larger than 3e-18, compensating for the maximum multiplicative error in the invariant
            // computation.
            uint256 virtInOver = balanceIn.add(virtualOffset.mulUp(GyroFixedPoint.ONE + 2));
            uint256 virtOutUnder = balanceOut.add(virtualOffset.mulDown(GyroFixedPoint.ONE - 1));

            amountOut = virtOutUnder.mulDown(amountIn).divDown(virtInOver.add(amountIn));
        }

        // Note that this in particular reverts if amountOut > balanceOut, i.e., if the out-amount would be more than
        // the balance.
        _require(amountOut <= balanceOut.mulDown(_MAX_OUT_RATIO), Errors.MAX_OUT_RATIO);
    }

    /** @dev Computes how many tokens must be sent to a pool in order to take `amountOut`, given the current balances
     * and price bounds. See documentation for _calcOutGivenIn(), too. */
    function _calcInGivenOut(
        uint256 balanceIn,
        uint256 balanceOut,
        uint256 amountOut,
        uint256 virtualOffset
    ) internal pure returns (uint256 amountIn) {
        /**********************************************************************************************
        // Described for X = `in' asset and Z = `out' asset, but equivalent for the other case       //
        // dX = incrX  = amountIn  > 0                                                               //
        // dZ = incrZ = amountOut < 0                                                                //
        // x = balanceIn             x' = x +  virtualOffset                                         //
        // z = balanceOut            z' = z +  virtualOffset                                         //
        // L  = inv.Liq            /            x' * z'          \             x' * dZ               //
        //                   dX = |   --------------------------  | - x' = ---------------           //
        //  x' = virtIn            \          ( z' + dZ)         /             z' - dZ               //
        //  z' = virtOut                                                                             //
        // Note that dz < 0 < dx.                                                                    //
        // We exploit the fact that this formula is symmetric and does not depend on which asset is  //
        // which.
        // We assume that the virtualOffset carries a relative +/- 3e-18 error due to the invariant  //
        // calculation add an appropriate safety margin.                                             //
        **********************************************************************************************/

        // Note that this in particular reverts if amountOut > balanceOut, i.e., if the trader tries to take more out of
        // the pool than is in it.
        _require(amountOut <= balanceOut.mulDown(_MAX_OUT_RATIO), Errors.MAX_OUT_RATIO);

        {
            // The factors in total lead to a multiplicative "safety margin" between the employed virtual offsets
            // very slightly larger than 3e-18, compensating for the maximum multiplicative error in the invariant
            // computation.
            uint256 virtInOver = balanceIn.add(virtualOffset.mulUp(GyroFixedPoint.ONE + 2));
            uint256 virtOutUnder = balanceOut.add(virtualOffset.mulDown(GyroFixedPoint.ONE - 1));

            amountIn = virtInOver.mulUp(amountOut).divUp(virtOutUnder.sub(amountOut));
        }

        _require(amountIn <= balanceIn.mulDown(_MAX_IN_RATIO), Errors.MAX_IN_RATIO);
    }
}
