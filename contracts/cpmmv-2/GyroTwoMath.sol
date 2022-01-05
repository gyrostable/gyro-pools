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

library GyroTwoMath {
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

    // Invariant is used to collect protocol swap fees by comparing its value between two times.
    // So we can round always to the same direction. It is also used to initiate the BPT amount
    // and, because there is a minimum BPT, we round down the invariant.
    function _calculateInvariant(
        uint256[] memory balances,
        uint256 sqrtAlpha,
        uint256 sqrtBeta
    ) internal pure returns (uint256) {
        /**********************************************************************************************
        // Calculate with quadratic formula
        // 0 = (1-sqrt(alhpa/beta)*L^2 - (y/sqrt(beta)+x*sqrt(alpha))*L - x*y)
        // 0 = a*L^2 + b*L + c
        // c < 0 , b < 0                                          (1/2)
        //                                  b + (b^2 + 4 * a * c)^                      //
        //                   L =    ------------------------------------------          //
        //                                          2 * a                               //
        //                                                                              //
        **********************************************************************************************/
        (uint256 a, uint256 b, uint256 c) = _calculateQuadraticTerms(
            balances,
            sqrtAlpha,
            sqrtBeta
        );
        return _calculateQuadratic(a, b, c);
    }

    function _calculateQuadraticTerms(
        uint256[] memory balances,
        uint256 sqrtAlpha,
        uint256 sqrtBeta
    )
        internal
        pure
        returns (
            uint256 a,
            uint256 b,
            uint256 c
        )
    {
        a = FixedPoint.ONE.sub(sqrtAlpha.divDown(sqrtBeta));
        uint256 bterm0 = balances[1].divDown(sqrtBeta);
        uint256 bterm1 = balances[0].mulDown(sqrtAlpha);
        b = bterm0.add(bterm1);
        c = balances[0].mulDown(balances[1]);
    }

    function _calculateQuadratic(
        uint256 a,
        uint256 b,
        uint256 c
    ) internal pure returns (uint256 invariant) {
        // c < 0 , b < 0
        uint256 denominator = a.mulDown(2 * FixedPoint.ONE);
        uint256 bSquare = b.mulDown(b);
        uint256 addTerm = a.mulDown(c.mulDown(4 * FixedPoint.ONE));
        uint256 radicand = bSquare.add(addTerm);
        uint256 sqrResult = _squareRoot(radicand);
        uint256 numerator = b.add(sqrResult);
        invariant = numerator.divDown(denominator);
    }

    function _squareRoot(uint256 input) internal pure returns (uint256 result) {
        result = input.powDown(FixedPoint.ONE / 2);
    }

    function _liquidityInvariantUpdate(
        uint256[] memory balances,
        uint256 sqrtAlpha,
        uint256 sqrtBeta,
        uint256 lastInvariant,
        uint256 incrY,
        bool isIncreaseLiq
    ) internal pure returns (uint256 invariant) {
        /**********************************************************************************************
      // Algorithm in 2.2.2 Liquidity Update                                                       //
      // Assumed that the  liquidity provided is correctly balanced                                //
      // dL = incrL  = Liquidity                                                                   //
      // dY = incrY = amountOut < 0                                                                //
      // sqrtPx = Squared Price              sqrtPx =  L / x'                                      //
      // x' = virtual reserves X                                                                   //
      //                                /              dY             \                            //
      //                    dL =       |   --------------------------  |                           //
      //                               \    ( sqrtPx - sqrtAlpha)     /                            //
      //                                                                                           //
      **********************************************************************************************/
        uint256 virtualX = balances[0] + lastInvariant.divUp(sqrtBeta);
        uint256 sqrtPrice = _calculateSqrtPrice(lastInvariant, virtualX);
        uint256 denominator = sqrtPrice.sub(sqrtAlpha);
        uint256 diffInvariant = incrY.divDown(denominator);
        invariant = isIncreaseLiq
            ? lastInvariant.add(diffInvariant)
            : lastInvariant.sub(diffInvariant);
    }

    // Computes how many tokens can be taken out of a pool if `amountIn` are sent, given the
    // current balances and weights.
    // virtualParamIn and virtualParamOut should be the virtual reserve offsets L/sqrt(beta) and L*sqrt(alpha) (depending on what the 'in' and 'out' token is, respectively)
    // Changed signs compared to original algorithm to account for dy < 0
    function _calcOutGivenIn(
        uint256 balanceIn,
        uint256 balanceOut,
        uint256 amountIn,
        uint256 virtualParamIn,
        uint256 virtualParamOut,
        uint256 currentInvariant
    ) internal pure returns (uint256) {
        /**********************************************************************************************
      // dX = incrX  = amountIn  > 0                                                               //
      // dY = incrY = amountOut < 0                                                                //
      // x = balanceIn             x' = x +  virtualParamX                                         //
      // y = balanceOut            y' = y +  virtualParamY                                         //
      // L  = inv.Liq                   /              L^2            \                            //
      //                   - dy = y' - |   --------------------------  |                           //
      //  x' = virtIn                   \          ( x' + dX)         /                            //
      //  y' = virtOut                                                                             //
      // Note that -dy > 0 is what the trader receives.                                            //
      // We exploit the fact that this formula is symmetric up to virtualParam{X,Y}.               //
      **********************************************************************************************/

        _require(
            amountIn <= balanceIn.mulDown(_MAX_IN_RATIO),
            Errors.MAX_IN_RATIO
        );
        uint256 virtIn = balanceIn.add(virtualParamIn);
        uint256 denominator = virtIn.add(amountIn);
        uint256 invSquare = currentInvariant.mulUp(currentInvariant);
        uint256 subtrahend = invSquare.divUp(denominator);
        uint256 virtOut = balanceOut.add(virtualParamOut);
        return virtOut.sub(subtrahend);
    }

    // Computes how many tokens must be sent to a pool in order to take `amountOut`, given the
    // current balances and weights.
    // Similar to the one before but adapting bc negative values

    function _calcInGivenOut(
        uint256 balanceIn,
        uint256 balanceOut,
        uint256 amountOut,
        uint256 virtualParamIn,
        uint256 virtualParamOut,
        uint256 currentInvariant
    ) internal pure returns (uint256) {
        /**********************************************************************************************
      // dX = incrX  = amountIn  > 0                                                               //
      // dY = incrY = amoountOut < 0                                                               //
      // x = balanceIn             x' = x +  virtualParamX                                         //
      // y = balanceOut            y' = y +  virtualParamY                                         //
      // x = balanceIn                                                                             //
      // L  = inv.Liq                /              L^2             \                              //
      //                     dx =   |   --------------------------  |  -  x'                       //
      // x' = virtIn                \         ( y' + dy)           /                               //
      // y' = virtOut                                                                              //
      // Note that dy < 0 < dx.                                                                    //
      **********************************************************************************************/
        _require(
            amountOut <= balanceOut.mulDown(_MAX_OUT_RATIO),
            Errors.MAX_OUT_RATIO
        );
        uint256 virtOut = balanceOut.add(virtualParamOut);
        uint256 denominator = virtOut.sub(amountOut);
        uint256 invSquare = currentInvariant.mulUp(currentInvariant);
        uint256 term = invSquare.divUp(denominator);
        uint256 virtIn = balanceIn.add(virtualParamIn);
        return term.sub(virtIn);
    }

    function _calcBptOutGivenExactTokensIn(
        uint256[] memory balances,
        uint256[] memory normalizedWeights,
        uint256[] memory amountsIn,
        uint256 bptTotalSupply,
        uint256 swapFeePercentage
    ) internal pure returns (uint256, uint256[] memory) {
        // BPT out, so we round down overall.

        uint256[] memory balanceRatiosWithFee = new uint256[](amountsIn.length);

        uint256 invariantRatioWithFees = 0;
        for (uint256 i = 0; i < balances.length; i++) {
            balanceRatiosWithFee[i] = balances[i].add(amountsIn[i]).divDown(
                balances[i]
            );
            invariantRatioWithFees = invariantRatioWithFees.add(
                balanceRatiosWithFee[i].mulDown(normalizedWeights[i])
            );
        }

        (
            uint256 invariantRatio,
            uint256[] memory swapFees
        ) = _computeJoinExactTokensInInvariantRatio(
                balances,
                normalizedWeights,
                amountsIn,
                balanceRatiosWithFee,
                invariantRatioWithFees,
                swapFeePercentage
            );

        uint256 bptOut = (invariantRatio > FixedPoint.ONE)
            ? bptTotalSupply.mulDown(invariantRatio.sub(FixedPoint.ONE))
            : 0;
        return (bptOut, swapFees);
    }

    /**
     * @dev Intermediate function to avoid stack-too-deep errors.
     */
    function _computeJoinExactTokensInInvariantRatio(
        uint256[] memory balances,
        uint256[] memory normalizedWeights,
        uint256[] memory amountsIn,
        uint256[] memory balanceRatiosWithFee,
        uint256 invariantRatioWithFees,
        uint256 swapFeePercentage
    ) private pure returns (uint256 invariantRatio, uint256[] memory swapFees) {
        // Swap fees are charged on all tokens that are being added in a larger proportion than the overall invariant
        // increase.
        swapFees = new uint256[](amountsIn.length);
        invariantRatio = FixedPoint.ONE;

        for (uint256 i = 0; i < balances.length; i++) {
            uint256 amountInWithoutFee;

            if (balanceRatiosWithFee[i] > invariantRatioWithFees) {
                uint256 nonTaxableAmount = balances[i].mulDown(
                    invariantRatioWithFees.sub(FixedPoint.ONE)
                );
                uint256 taxableAmount = amountsIn[i].sub(nonTaxableAmount);
                uint256 swapFee = taxableAmount.mulUp(swapFeePercentage);

                amountInWithoutFee = nonTaxableAmount.add(
                    taxableAmount.sub(swapFee)
                );
                swapFees[i] = swapFee;
            } else {
                amountInWithoutFee = amountsIn[i];
            }

            uint256 balanceRatio = balances[i].add(amountInWithoutFee).divDown(
                balances[i]
            );

            invariantRatio = invariantRatio.mulDown(
                balanceRatio.powDown(normalizedWeights[i])
            );
        }
    }

    function _calcTokenInGivenExactBptOut(
        uint256 balance,
        uint256 normalizedWeight,
        uint256 bptAmountOut,
        uint256 bptTotalSupply,
        uint256 swapFeePercentage
    ) internal pure returns (uint256 amountIn, uint256 swapFee) {
        /******************************************************************************************
        // tokenInForExactBPTOut                                                                 //
        // a = amountIn                                                                          //
        // b = balance                      /  /    totalBPT + bptOut      \    (1 / w)       \  //
        // bptOut = bptAmountOut   a = b * |  | --------------------------  | ^          - 1  |  //
        // bpt = totalBPT                   \  \       totalBPT            /                  /  //
        // w = weight                                                                            //
        ******************************************************************************************/

        // Token in, so we round up overall.

        // Calculate the factor by which the invariant will increase after minting BPTAmountOut
        uint256 invariantRatio = bptTotalSupply.add(bptAmountOut).divUp(
            bptTotalSupply
        );
        _require(
            invariantRatio <= _MAX_INVARIANT_RATIO,
            Errors.MAX_OUT_BPT_FOR_TOKEN_IN
        );

        // Calculate by how much the token balance has to increase to match the invariantRatio
        uint256 balanceRatio = invariantRatio.powUp(
            FixedPoint.ONE.divUp(normalizedWeight)
        );

        uint256 amountInWithoutFee = balance.mulUp(
            balanceRatio.sub(FixedPoint.ONE)
        );

        // We can now compute how much extra balance is being deposited and used in virtual swaps, and charge swap fees
        // accordingly.
        uint256 taxablePercentage = normalizedWeight.complement();
        uint256 taxableAmount = amountInWithoutFee.mulUp(taxablePercentage);
        uint256 nonTaxableAmount = amountInWithoutFee.sub(taxableAmount);

        uint256 taxableAmountPlusFees = taxableAmount.divUp(
            FixedPoint.ONE.sub(swapFeePercentage)
        );

        swapFee = taxableAmountPlusFees - taxableAmount;
        amountIn = nonTaxableAmount.add(taxableAmountPlusFees);
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

    function _calcBptInGivenExactTokensOut(
        uint256[] memory balances,
        uint256[] memory normalizedWeights,
        uint256[] memory amountsOut,
        uint256 bptTotalSupply,
        uint256 swapFeePercentage
    ) internal pure returns (uint256, uint256[] memory) {
        // BPT in, so we round up overall.

        uint256[] memory balanceRatiosWithoutFee = new uint256[](
            amountsOut.length
        );
        uint256 invariantRatioWithoutFees = 0;
        for (uint256 i = 0; i < balances.length; i++) {
            balanceRatiosWithoutFee[i] = balances[i].sub(amountsOut[i]).divUp(
                balances[i]
            );
            invariantRatioWithoutFees = invariantRatioWithoutFees.add(
                balanceRatiosWithoutFee[i].mulUp(normalizedWeights[i])
            );
        }

        (
            uint256 invariantRatio,
            uint256[] memory swapFees
        ) = _computeExitExactTokensOutInvariantRatio(
                balances,
                normalizedWeights,
                amountsOut,
                balanceRatiosWithoutFee,
                invariantRatioWithoutFees,
                swapFeePercentage
            );

        uint256 bptIn = bptTotalSupply.mulUp(invariantRatio.complement());
        return (bptIn, swapFees);
    }

    /**
     * @dev Intermediate function to avoid stack-too-deep errors.
     */
    function _computeExitExactTokensOutInvariantRatio(
        uint256[] memory balances,
        uint256[] memory normalizedWeights,
        uint256[] memory amountsOut,
        uint256[] memory balanceRatiosWithoutFee,
        uint256 invariantRatioWithoutFees,
        uint256 swapFeePercentage
    ) private pure returns (uint256 invariantRatio, uint256[] memory swapFees) {
        swapFees = new uint256[](amountsOut.length);
        invariantRatio = FixedPoint.ONE;

        for (uint256 i = 0; i < balances.length; i++) {
            // Swap fees are typically charged on 'token in', but there is no 'token in' here, so we apply it to
            // 'token out'. This results in slightly larger price impact.

            uint256 amountOutWithFee;
            if (invariantRatioWithoutFees > balanceRatiosWithoutFee[i]) {
                uint256 nonTaxableAmount = balances[i].mulDown(
                    invariantRatioWithoutFees.complement()
                );
                uint256 taxableAmount = amountsOut[i].sub(nonTaxableAmount);
                uint256 taxableAmountPlusFees = taxableAmount.divUp(
                    FixedPoint.ONE.sub(swapFeePercentage)
                );

                swapFees[i] = taxableAmountPlusFees - taxableAmount;
                amountOutWithFee = nonTaxableAmount.add(taxableAmountPlusFees);
            } else {
                amountOutWithFee = amountsOut[i];
            }

            uint256 balanceRatio = balances[i].sub(amountOutWithFee).divDown(
                balances[i]
            );

            invariantRatio = invariantRatio.mulDown(
                balanceRatio.powDown(normalizedWeights[i])
            );
        }
    }

    function _calcTokenOutGivenExactBptIn(
        uint256 balance,
        uint256 normalizedWeight,
        uint256 bptAmountIn,
        uint256 bptTotalSupply,
        uint256 swapFeePercentage
    ) internal pure returns (uint256 amountOut, uint256 swapFee) {
        /*****************************************************************************************
        // exactBPTInForTokenOut                                                                //
        // a = amountOut                                                                        //
        // b = balance                     /      /    totalBPT - bptIn       \    (1 / w)  \   //
        // bptIn = bptAmountIn    a = b * |  1 - | --------------------------  | ^           |  //
        // bpt = totalBPT                  \      \       totalBPT            /             /   //
        // w = weight                                                                           //
        *****************************************************************************************/

        // Token out, so we round down overall. The multiplication rounds down, but the power rounds up (so the base
        // rounds up). Because (totalBPT - bptIn) / totalBPT <= 1, the exponent rounds down.

        // Calculate the factor by which the invariant will decrease after burning BPTAmountIn
        uint256 invariantRatio = bptTotalSupply.sub(bptAmountIn).divUp(
            bptTotalSupply
        );
        _require(
            invariantRatio >= _MIN_INVARIANT_RATIO,
            Errors.MIN_BPT_IN_FOR_TOKEN_OUT
        );

        // Calculate by how much the token balance has to decrease to match invariantRatio
        uint256 balanceRatio = invariantRatio.powUp(
            FixedPoint.ONE.divDown(normalizedWeight)
        );

        // Because of rounding up, balanceRatio can be greater than one. Using complement prevents reverts.
        uint256 amountOutWithoutFee = balance.mulDown(
            balanceRatio.complement()
        );

        // We can now compute how much excess balance is being withdrawn as a result of the virtual swaps, which result
        // in swap fees.
        uint256 taxablePercentage = normalizedWeight.complement();

        // Swap fees are typically charged on 'token in', but there is no 'token in' here, so we apply it
        // to 'token out'. This results in slightly larger price impact. Fees are rounded up.
        uint256 taxableAmount = amountOutWithoutFee.mulUp(taxablePercentage);
        uint256 nonTaxableAmount = amountOutWithoutFee.sub(taxableAmount);

        swapFee = taxableAmount.mulUp(swapFeePercentage);
        amountOut = nonTaxableAmount.add(taxableAmount.sub(swapFee));
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

    function _calcDueTokenProtocolSwapFeeAmount(
        uint256 balance,
        uint256 normalizedWeight,
        uint256 previousInvariant,
        uint256 currentInvariant,
        uint256 protocolSwapFeePercentage
    ) internal pure returns (uint256) {
        /*********************************************************************************
        /*  protocolSwapFeePercentage * balanceToken * ( 1 - (previousInvariant / currentInvariant) ^ (1 / weightToken))
        *********************************************************************************/

        if (currentInvariant <= previousInvariant) {
            // This shouldn't happen outside of rounding errors, but have this safeguard nonetheless to prevent the Pool
            // from entering a locked state in which joins and exits revert while computing accumulated swap fees.
            return 0;
        }

        // We round down to prevent issues in the Pool's accounting, even if it means paying slightly less in protocol
        // fees to the Vault.

        // Fee percentage and balance multiplications round down, while the subtrahend (power) rounds up (as does the
        // base). Because previousInvariant / currentInvariant <= 1, the exponent rounds down.

        uint256 base = previousInvariant.divUp(currentInvariant);
        uint256 exponent = FixedPoint.ONE.divDown(normalizedWeight);

        // Because the exponent is larger than one, the base of the power function has a lower bound. We cap to this
        // value to avoid numeric issues, which means in the extreme case (where the invariant growth is larger than
        // 1 / min exponent) the Pool will pay less in protocol fees than it should.
        base = Math.max(base, FixedPoint.MIN_POW_BASE_FREE_EXPONENT);

        uint256 power = base.powUp(exponent);

        uint256 tokenAccruedFees = balance.mulDown(power.complement());
        return tokenAccruedFees.mulDown(protocolSwapFeePercentage);
    }

    function _calculateVirtualParameter0(uint256 invariant, uint256 _sqrtBeta)
        internal
        pure
        returns (uint256)
    {
        return invariant.divDown(_sqrtBeta);
    }

    function _calculateVirtualParameter1(uint256 invariant, uint256 _sqrtAlpha)
        internal
        pure
        returns (uint256)
    {
        return invariant.mulDown(_sqrtAlpha);
    }

    function _calculateSqrtPrice(uint256 invariant, uint256 virtualX)
        internal
        pure
        returns (uint256)
    {
        /*********************************************************************************
      /*  sqrtPrice =  L / x'
      *********************************************************************************/
        return invariant.divDown(virtualX);
    }
}
