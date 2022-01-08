
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

// These functions start with an underscore, as if they were part of a contract and not a library. At some point this
// should be fixed.
// solhint-disable private-vars-leading-underscore

library GyroThreeMath {
    using FixedPoint for uint256;
    // A minimum normalized weight imposes a maximum weight ratio. We need this due to limitations in the
    // implementation of the power function, as these ratios are often exponents.
    uint256 internal constant _MIN_WEIGHT = 0.01e18;
    // Having a minimum normalized weight imposes a limit on the maximum number of tokens;
    // i.e., the largest possible pool is one where all tokens have exactly the minimum weight.
    uint256 internal constant _MAX_WEIGHTED_TOKENS = 100;

    // Pool limits that arise from limitations in the fixed point power function (and the imposed 1:100 maximum weight
    // ratio).

    // Swap limits: amounts swapped may not be larger than this percentage of total balance.
    uint256 internal constant _MAX_IN_RATIO = 0.3e18;
    uint256 internal constant _MAX_OUT_RATIO = 0.3e18;

    // Invariant growth limit: non-proportional joins cannot cause the invariant to increase by more than this ratio.
    uint256 internal constant _MAX_INVARIANT_RATIO = 3e18;
    // Invariant shrink limit: non-proportional exits cannot cause the invariant to decrease by less than this ratio.
    uint256 internal constant _MIN_INVARIANT_RATIO = 0.7e18;

    // About swap fees on joins and exits:
    // Any join or exit that is not perfectly balanced (e.g. all single token joins or exits) is mathematically
    // equivalent to a perfectly balanced join or  exit followed by a series of swaps. Since these swaps would charge
    // swap fees, it follows that (some) joins and exits should as well.
    // On these operations, we split the token amounts in 'taxable' and 'non-taxable' portions, where the 'taxable' part
    // is the one to which swap fees are applied.

    // TODO code for _calculateInvariant to be moved over from the experiments repo (`cpmmv-3` repo), contract version of the code.

    // Invariant is used to collect protocol swap fees by comparing its value between two times.
    // So we can round always to the same direction. It is also used to initiate the BPT amount
    // and, because there is a minimum BPT, we round down the invariant.
    // TODO alpha -> alpha3root
    function _calculateInvariant(uint256[] memory balances, uint256 alpha)
        internal
        pure
        returns (uint256)
    {
        /**********************************************************************************************
        // Calculate with cubic formula
        // TODO: need a way to tackle complex number in _calculateCubic
        **********************************************************************************************/
        (uint256 a, uint256 b, uint256 c, uint256 d) = _calculateCubicTerms(
            balances,
            alpha
        );
        return _calculateCubic(a, b, c, d);
    }

    // a > 0, b < 0, c < 0, d < 0
    function _calculateCubicTerms(uint256[] memory balances, uint256 alpha)
        internal
        pure
        returns (
            uint256 a,
            uint256 b,
            uint256 c,
            uint256 d
        )
    {
        // TODO it's prob more efficient to compute alpha^1/3 once, then only square later. (saves one fractional powDown)
        // TODO review all Up/Down.
        a = FixedPoint.ONE.sub(alpha);
        uint256 bterm = balances[0].add(balances[1]).add(balances[2]);
        b = bterm.mulDown(alpha.powDown((2 * FixedPoint.ONE) / 3));
        uint256 cterm = (balances[0].mulDown(balances[1]))
            .add(balances[1].mulDown(balances[2]))
            .add(balances[2].mulDown(balances[0]));
        c = cterm.mulDown(alpha.powDown(FixedPoint.ONE / 3));
        d = balances[0].mulDown(balances[1]).mulDown(balances[2]);
    }

    function _calculateCubic(
        uint256 a,
        uint256 mb,
        uint256 mc,
        uint256 md
    ) internal pure returns (uint256 l) {
        // a > 0 , b < 0, c < 0, d < 0
        // Only absolute values are provided. `mb` is -b, etc.
        // For TESTING. EXPERIMENTAL!
        // TODO review rounding directions (Up vs Down)

        // Starting point:
        uint256 radic = mb.mulUp(mb) + a.mulUp(mc).mulUp(3 * FixedPoint.ONE);
        // TODO maybe swap out sqrt implementation. This is Daniel's hack.
        l =
            mb.divUp(a * 3) +
            radic.powUp(FixedPoint.ONE / 2).divUp(a * 3) *
            ((3 * FixedPoint.ONE) / 2);

        // TODO evaluation is not super optimized yet
        // Note that f(l) may be negative for the first iteration and will then be positive. f'(l) is always positive.
        // TODO some check against numerical issues and/or gas issues would be good:
        // - define limit for steps.
        // - check if we were at an f(l)-positive point before and now are negative. This shouldn't happen, prob stop.
        while (true) {
            // f(l) can be positive or negative, so we represent the positive and negative part separately (we know which ones those are)
            // TODO review Up / Down
            uint256 f_l_plus = a.mulUp(l).mulUp(l).mulUp(l);
            uint256 f_l_minus = mb.mulUp(l).mulUp(l).add(mc.mulUp(l)).add(md);
            uint256 df_l = (3 * a).mulUp(l).mulUp(l).sub((2 * mb).mulUp(l)).sub(
                mc
            ); // Trust the math this doesn't create an undeflow. It really shouldn't.
            if (f_l_plus < f_l_minus) {
                // f(l) < 0
                // delta is always non-negative here, but we use it differently.
                uint256 delta = f_l_minus.sub(f_l_plus).divDown(df_l);
                if (delta == 0) return l;
                l = l.add(delta);
            } else {
                // f_l_plus >= f_l_minus
                uint256 delta = f_l_plus.sub(f_l_minus).divDown(df_l);
                if (delta == 0) return l;
                l = l.sub(delta);
            }
        }
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
