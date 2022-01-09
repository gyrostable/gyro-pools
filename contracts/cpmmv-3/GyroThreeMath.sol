
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
    uint256 internal constant _MAX_IN_RATIO = 0.3e18;
    uint256 internal constant _MAX_OUT_RATIO = 0.3e18;

    uint8 internal constant _INVARIANT_SHRINKING_FACTOR_PER_STEP = 10;

    // Invariant is used to collect protocol swap fees by comparing its value between two times.
    // So we can round always to the same direction. It is also used to initiate the BPT amount
    // and, because there is a minimum BPT, we round down the invariant.
    function _calculateInvariant(uint256[] memory balances, uint256 root3Alpha)
        internal
        pure
        returns (uint256)
    {
        (uint256 a, uint256 mb, uint256 mc, uint256 md) = _calculateCubicTerms(balances, root3Alpha);
        return _calculateCubic(a, mb, mc, md);
    }

    // a > 0, b < 0, c < 0, d < 0
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
        uint256 alpha23 = root3Alpha.mulDown(root3Alpha);  // alpha to the power of (2/3)
        uint256 alpha = alpha23.mulDown(root3Alpha);
        a = FixedPoint.ONE.sub(alpha);
        uint256 bterm = balances[0].add(balances[1]).add(balances[2]);
        mb = bterm.mulDown(alpha23);
        uint256 cterm = (balances[0].mulDown(balances[1]))
            .add(balances[1].mulDown(balances[2]))
            .add(balances[2].mulDown(balances[0]));
        mc = cterm.mulDown(root3Alpha);
        md = balances[0].mulDown(balances[1]).mulDown(balances[2]);
    }

    // Calculate the maximal root of the polynomial a L^3 - mb L^2 - mc L - md.
    // This root is always non-negative, and it is the unique positive root unless mb == mc == md == 0.
    function _calculateCubic(
        uint256 a,
        uint256 mb,
        uint256 mc,
        uint256 md
    ) internal pure returns (uint256 l) {
        if (md == 0) {
            // lower-order special case
            uint256 radic = mb.mulDown(mb).add(4*a.mulDown(mc));
            l = mb.add(radic.powDown(FixedPoint.ONE / 2)).divDown(2*a);
        } else {
            l = _calculateCubicStartingPoint(a, mb, mc, md);
            l = _runNewtonIteration(a, mb, mc, md, l);
        }
    }

    // Starting point for Newton iteration. Safe with all cubic polynomials where the coefficients have the appropriate
    // signs, but calibrated to the particular polynomial for computing the invariant.
    function _calculateCubicStartingPoint(uint256 a, uint256 mb, uint256 mc, uint256 md) internal pure returns (uint256 l0) {
        uint256 radic = mb.mulUp(mb).add(a.mulUp(mc).mulUp(3*FixedPoint.ONE));
        uint256 lmin = mb.divUp(a * 3) + radic.powUp(FixedPoint.ONE / 2).divUp(a * 3);
        // The factor 3/2 is a magic number found experimentally for our invariant. All factors > 1 are safe.
        l0 = lmin.mulUp(3 * FixedPoint.ONE / 2); 
    }

    // Find a root of the given polynomial with the given starting point l.
    // Safe iff l > the local minimum.
    // Note that f(l) may be negative for the first iteration and will then be positive (up to rounding errors).
    // f'(l) is always positive for the range of values we consider.
    // todo maybe define a limit on the number of steps? (careful with exploits though! - maybe this is bad
    // practice?)
    // TODO maybe add check against numerical issues:
    // - check if delta increased from one step to the next. Again, this shouldn't happen.
    // As our stopping condition, we use that delta=0 or we are going upwards in l even though we've previously been
    // going downwards. By convexity of the function, this should never happen and this means that numerical error
    // now dominates what we do, and we stop. This is more robust than any fixed threshold on the step size or value
    // of f, for which we can always find sufficiently large numbers where we are always above the threshold.
    function _runNewtonIteration (uint256 a, uint256 mb, uint256 mc, uint256 md, uint256 l)
            pure internal returns (uint256) {
        uint256 delta_abs_prev = l;
        for (uint256 i = 0; i < 255; ++i) {
            // The delta to the next step can be positive or negative, so we represent a positive and a negative part
            // separately. The signed delta is delta_plus - delta_minus, but we only ever consider its absolute value.
            (uint256 delta_abs, bool delta_is_pos) =  _calcNewtonDelta(a, mb, mc, md, l);
            if (delta_abs == 0 || (iteration > 0 && delta_is_pos))  // literally stopped or numerical error dominates
                return l;
            if (delta_abs > delta_abs_prev / _INVARIANT_SHRINKING_FACTOR_PER_STEP) {  // stalled
                return l - delta_abs;  // Move one more step to the left to ensure we're underestimating L
                // TODO:
                //
                // We've converged. Now move to the left until f(L) is negative to make sure we slightly underestimate,
                // rather than overestimate, the invariant. It is not trivial to check if f(L) < 0 because computing
                // f(L) can involve some rather large numbers. Instead, we use our existing Newton step function to
                // do this. Importantly, we use our existing Newton step width, not the newly computed one, as the step
                // width!
                // for (uint256 j = 0; j < 255; ++j) {
                //     (, delta_is_pos) = _calcNewtonDelta(a, mb, mc, md, l)
                //     if (delta_is_pos)
                //         return
                //     l -= delta_abs
                // }
                // _revert(GyroThreePoolErrors.INVARIANT_DIDNT_CONVERGE);
            }
            delta_abs_prev = delta_abs;
            if (delta_is_pos)
                l = l.add(delta_abs);
            else
                l = l.sub(delta_abs);
        }
        _revert(GyroThreePoolErrors.INVARIANT_DIDNT_CONVERGE);
    }

    // -f(l)/f'(l), represented as an absolute value and a sign. Require that l is sufficiently large so that f is strictly increasing.
    function _calcNewtonDelta(uint256 a, uint256 mb, uint256 mc, uint256 md, uint256 l)
            pure internal returns (uint256 delta_abs, bool delta_is_pos) {
        uint256 df_l = (3 * a).mulUp(l).sub(2 * mb).mulUp(l).sub(mc);  // Does not underflow since l >> 0 by assumption.
        // We know that a l^2 / df_l ~ 1. (this is pretty exact actually, see the Mathematica notebook). We use this
        // multiplication order to prevent overflows that can otherwise occur when computing l^3 for very large
        // reserves.
        uint256 delta_minus = a.mulUp(l).mulUp(l);
        delta_minus = delta_minus.divUp(df_l).mulUp(l);
        // use multiple statements to prevent 'stack too deep'. The order of operations is chosen to prevent overflows
        // for very large numbers.
        uint256 delta_plus = mb.mulUp(l).add(mc).divUp(df_l);
        delta_plus = delta_plus.mulUp(l).add(md.divUp(df_l));

        delta_is_pos = (delta_plus >= delta_minus);
        delta_abs = (delta_is_pos ? delta_plus - delta_minus : delta_minus - delta_plus);
    }


    // TODO check corner cases (zero real reserves for instance)
    /** @dev New invariant assuming that the balances increase from 'lastBalances', where the invariant was
      * 'lastInvariant', to some new value, where the 'z' component (asset index 2) changes by 'deltaZ' and the other
      * assets change, too, in such a way that the prices stay the same. 'isIncreaseLiq' captures the sign of the change
      * (true meaning positive).
      * We apply Proposition 10 from the writeup. */
    function _liquidityInvariantUpdate(
        uint256[] memory lastBalances,
        uint256 root3Alpha,
        uint256 lastInvariant,
        uint256 incrZ,
        bool isIncreaseLiq
    ) internal pure returns (uint256 invariant) {
        uint256 virtualOffset = lastInvariant.mulDown(root3Alpha);
        uint256 virtX = lastBalances[0].add(virtualOffset);
        uint256 virtY = lastBalances[1].add(virtualOffset);
        uint256 cbrtPrice = _calculateCbrtPrice(
            lastInvariant,
            virtX,
            virtY
        );
        uint256 denominator = cbrtPrice.sub(root3Alpha);
        uint256 diffInvariant = incrZ.divDown(denominator);
        invariant = isIncreaseLiq
            ? lastInvariant.add(diffInvariant)
            : lastInvariant.sub(diffInvariant);
    }

    /** @dev Computes how many tokens can be taken out of a pool if `amountIn` are sent, given the
     * current balances and weights.
     * Changed signs compared to original algorithm to account for amountOut < 0.
     * See Proposition 12.*/
    function _calcOutGivenIn(
        uint256 balanceIn,
        uint256 balanceOut,
        uint256 amountIn,
        uint256 virtualOffsetInOut
    ) internal pure returns (uint256 amountOut) {
        _require(
            amountIn <= balanceIn.mulDown(_MAX_IN_RATIO),
            Errors.MAX_IN_RATIO
        );

        uint256 virtIn = balanceIn.add(virtualOffsetInOut);
        uint256 virtOut = balanceOut.add(virtualOffsetInOut);
        uint256 denominator = virtIn.add(amountOut);
        uint256 subtrahend = virtIn.mulDown(virtOut).divDown(denominator);

        _require(
            virtOut <= subtrahend,
            Errors.INSUFFICIENT_INTERNAL_BALANCE  // TODO is this the right error code?
        );
        amountOut = virtOut.sub(subtrahend);
    }

    /* @dev Computes how many tokens must be sent to a pool in order to take `amountOut`, given the
     * currhent balances and weights.
     * Similar to the one before but adapting bc negative values.*/
    function _calcInGivenOut(
        uint256 balanceIn,
        uint256 balanceOut,
        uint256 amountOut,
        uint256 virtualOffsetInOut
    ) internal pure returns (uint256 amountIn) {
        _require(
            amountOut <= balanceOut.mulDown(_MAX_OUT_RATIO),
            Errors.MAX_OUT_RATIO
        );
        // The following is subsumed by the above check, but let's keep it in just in case.
        _require(
            amountOut <= balanceOut,
            Errors.INSUFFICIENT_INTERNAL_BALANCE
        );

        uint256 virtIn = balanceIn.add(virtualOffsetInOut);
        uint256 virtOut = balanceOut.add(virtualOffsetInOut);
        uint256 denominator = virtOut.sub(amountOut);
        uint256 minuend = virtIn.mulDown(virtOut).divDown(denominator);

        // The following mathematically cannot underflow.
        amountIn = minuend.sub(virtIn);
    }

    function _calcAllTokensInGivenExactBptOut(
        uint256[] memory balances,
        uint256 bptAmountOut,
        uint256 totalBPT
    ) internal pure returns (uint256[] memory) {
        /************************************************************************************
        // tokensInForExactBptOut                                                          //
        // (per token)                                                                     //
        // aI = amountIn                   /   bptOut   \                                  //
        // b = balance           aI = b * | ------------ |                                 //
        // bptOut = bptAmountOut           \  totalBPT  /                                  //
        // bpt = totalBPT                                                                  //
        ************************************************************************************/

        // Tokens in, so we round up overall.
        uint256 bptRatio = bptAmountOut.divUp(totalBPT);

        uint256[] memory amountsIn = new uint256[](balances.length);
        for (uint256 i = 0; i < balances.length; i++) {
            amountsIn[i] = balances[i].mulUp(bptRatio);
        }

        return amountsIn;
    }

    function _calcTokensOutGivenExactBptIn(
        uint256[] memory balances,
        uint256 bptAmountIn,
        uint256 totalBPT
    ) internal pure returns (uint256[] memory) {
        /**********************************************************************************************
        // exactBPTInForTokensOut                                                                    //
        // (per token)                                                                               //
        // aO = amountOut                  /        bptIn         \                                  //
        // b = balance           a0 = b * | ---------------------  |                                 //
        // bptIn = bptAmountIn             \       totalBPT       /                                  //
        // bpt = totalBPT                                                                            //
        **********************************************************************************************/

        // Since we're computing an amount out, we round down overall. This means rounding down on both the
        // multiplication and division.

        uint256 bptRatio = bptAmountIn.divDown(totalBPT);

        uint256[] memory amountsOut = new uint256[](balances.length);
        for (uint256 i = 0; i < balances.length; i++) {
            amountsOut[i] = balances[i].mulDown(bptRatio);
        }

        return amountsOut;
    }

    /** @dev Cube root of the product of the prices of x and y. Helper value. See Lemma 4. */
    function _calculateCbrtPrice(
        uint256 invariant,
        uint256 virtualX,
        uint256 virtualY
    ) internal pure returns (uint256) {
      /*********************************************************************************
       *  cbrtPrice =  L^2 / x' y'
       ********************************************************************************/
        return invariant.divDown(virtualX).mulDown(invariant).divDown(virtualY);
    }
}

/** @dev Calculates protocol fees due to Gyro and Balancer
     *   Note: we do this differently than normal Balancer pools by paying fees in BPT tokens
     *   b/c this is much more gas efficient than doing many transfers of underlying assets
     *   This function gets protocol fee parameters from GyroConfig
     *
     *   This function is exactly equal to the corresponding one in GyroTwoMath.
     *   TODO someday maybe make one function or a little library for this.
     */
    function _calcProtocolFees(
        uint256 previousInvariant,
        uint256 currentInvariant,
        uint256 currentBptSupply,
        uint256 protocolSwapFeePerc,
        uint256 protocolFeeGyroPortion
    ) internal pure returns (uint256[] memory dueFees) {
        /*********************************************************************************
        /*  Protocol fee collection should decrease the invariant L by
        *        Delta L = protocolSwapFeePerc * (currentInvariant - previousInvariant)
        *   To take these fees in BPT LP shares, the protocol mints Delta S new LP shares where
        *        Delta S = S * Delta L / ( currentInvariant - Delta L )
        *   where S = current BPT supply
        *   The protocol then splits the fees (in BPT) considering protocolFeeGyroPortion
        *********************************************************************************/
        dueFees = new uint256[](2);

        if (currentInvariant <= previousInvariant) {
            // This shouldn't happen outside of rounding errors, but have this safeguard nonetheless to prevent the Pool
            // from entering a locked state in which joins and exits revert while computing accumulated swap fees.
            return dueFees;
        }

        // Calculate due protocol fees in BPT terms
        // We round down to prevent issues in the Pool's accounting, even if it means paying slightly less in protocol
        // fees to the Vault.
        // For the numerator, we need to round down delta L. Also for the denominator b/c subtracted
        uint256 diffInvariant = protocolSwapFeePerc.mulDown(
            currentInvariant.sub(previousInvariant)
        );
        uint256 numerator = diffInvariant.mulDown(currentBptSupply);
        uint256 denominator = currentInvariant.sub(diffInvariant);
        uint256 deltaS = numerator.divDown(denominator);

        // Split fees between Gyro and Balancer
        if (protocolFeeGyroPortion == 1e18) {
            dueFees[0] = deltaS;
        } else {
            dueFees[0] = protocolFeeGyroPortion.mulDown(deltaS);
            dueFees[1] = (FixedPoint.ONE.sub(protocolFeeGyroPortion)).mulDown(
                deltaS
            );
        }

        return dueFees;
    }