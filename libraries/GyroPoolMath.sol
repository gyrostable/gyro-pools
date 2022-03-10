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

library GyroPoolMath {
    using FixedPoint for uint256;

    // Note: this function is identical to that in WeightedMath.sol audited by Balancer
    function _calcAllTokensInGivenExactBptOut(
        uint256[] memory balances,
        uint256 bptAmountOut,
        uint256 totalBPT
    ) internal pure returns (uint256[] memory) {
        /************************************************************************************
        // tokensInForExactBptOut                                                          //
        // (per token)                                                                     //
        // aI = amountIn (vec)             /   bptOut   \                                  //
        // b = balance (vec)     aI = b * | ------------ |                                 //
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

    // Note: this function is identical to that in WeightedMath.sol audited by Balancer
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

    /** @dev Calculates protocol fees due to Gyro and Balancer
     *   Note: we do this differently than normal Balancer pools by paying fees in BPT tokens
     *   b/c this is much more gas efficient than doing many transfers of underlying assets
     *   This function gets protocol fee parameters from GyroConfig
     */
    function _calcProtocolFees(
        uint256 previousInvariant,
        uint256 currentInvariant,
        uint256 currentBptSupply,
        uint256 protocolSwapFeePerc,
        uint256 protocolFeeGyroPortion
    ) internal pure returns (uint256, uint256) {
        /*********************************************************************************
        /*  Protocol fee collection should decrease the invariant L by
        *        Delta L = protocolSwapFeePerc * (currentInvariant - previousInvariant)
        *   To take these fees in BPT LP shares, the protocol mints Delta S new LP shares where
        *        Delta S = S * Delta L / ( currentInvariant - Delta L )
        *   where S = current BPT supply
        *   The protocol then splits the fees (in BPT) considering protocolFeeGyroPortion
        *   See also the write-up, Proposition 7.
        *********************************************************************************/

        if (currentInvariant <= previousInvariant) {
            // This shouldn't happen outside of rounding errors, but have this safeguard nonetheless to prevent the Pool
            // from entering a locked state in which joins and exits revert while computing accumulated swap fees.
            return (0, 0);
        }

        // Calculate due protocol fees in BPT terms
        // We round down to prevent issues in the Pool's accounting, even if it means paying slightly less in protocol
        // fees to the Vault.
        // For the numerator, we need to round down delta L. Also for the denominator b/c subtracted
        // Ordering multiplications for best fixed point precision considering that S and currentInvariant-previousInvariant could be large
        uint256 numerator = (currentBptSupply.mulDown(currentInvariant.sub(previousInvariant))).mulDown(protocolSwapFeePerc);
        uint256 diffInvariant = protocolSwapFeePerc.mulDown(currentInvariant.sub(previousInvariant));
        uint256 denominator = currentInvariant.sub(diffInvariant);
        uint256 deltaS = numerator.divDown(denominator);

        // Split fees between Gyro and Balancer
        uint256 gyroFees = protocolFeeGyroPortion.mulDown(deltaS);
        uint256 balancerFees = deltaS.sub(gyroFees);

        return (gyroFees, balancerFees);
    }

    /** @dev If `deltaBalances` are such that, when changing `balances` by it, the price stays the same ("balanced
     * liquidity update"), then this returns the invariant after that change. This is more efficient than calling
     * `calculateInvariant()` on the updated balances. `isIncreaseLiq` denotes the sign of the update.
     * See the writeup, Corollary 3 in Section 2.1.5.
     */
    function liquidityInvariantUpdate(
        uint256[] memory balances,
        uint256 uinvariant,
        uint256[] memory deltaBalances,
        bool isIncreaseLiq
    ) internal pure returns (uint256 unewInvariant) {
        uint256 largestBalanceIndex;
        uint256 largestBalance;
        for (uint256 i = 0; i < balances.length; i++) {
            if (balances[i] > largestBalance) {
                largestBalance = balances[i];
                largestBalanceIndex = i;
            }
        }

        uint256 deltaInvariant = uinvariant.mulDown(deltaBalances[largestBalanceIndex]).divDown(balances[largestBalanceIndex]);
        unewInvariant = isIncreaseLiq ? uinvariant.add(deltaInvariant) : uinvariant.sub(deltaInvariant);
    }
    
        
    /** @dev Implements square root algorithm using Newton's method and a first-guess optimisation **/
    function _sqrt(uint256 input) internal pure returns (uint256) {
        if (input == 0) {
            return 0;
        }

        uint256 guess = _makeInitialGuess(input);
        uint256 minStepSize = 5;

        for (uint256 i = 0; i < 10; i++) {
            uint256 oldGuess = guess;
            guess = guess.add(input.divDown(guess)) / 2;

            if (
                (oldGuess > guess && oldGuess - guess < minStepSize) ||
                (oldGuess <= guess && guess - oldGuess < minStepSize)
            ) {
                break;
            }
        }

        return guess;
    }

    function _makeInitialGuess10(uint256 input) internal pure returns (uint256) {
        uint256 orderUpperBound = 72;
        uint256 orderLowerBound = 0;
        uint256 orderMiddle;

        orderMiddle = (orderUpperBound + orderLowerBound) / 2;

        while (orderUpperBound - orderLowerBound != 1) {
            if (10**orderMiddle > input) {
                orderUpperBound = orderMiddle;
            } else {
                orderLowerBound = orderMiddle;
            }
        }

        return 10**(orderUpperBound / 2);
    }

    function _makeInitialGuess(uint256 input) internal pure returns (uint256) {
        if (input >= FixedPoint.ONE) {
            return (1 << (intLog2Halved(input / FixedPoint.ONE))) * FixedPoint.ONE;
        } else {
            return FixedPoint.ONE / (1 << (intLog2Halved(FixedPoint.ONE / input) / 2));
        }
    }

    function intLog2Halved(uint256 x) public pure returns (uint256 n) {
        if (x >= 1 << 128) {
            x >>= 128;
            n += 64;
        }
        if (x >= 1 << 64) {
            x >>= 64;
            n += 32;
        }
        if (x >= 1 << 32) {
            x >>= 32;
            n += 16;
        }
        if (x >= 1 << 16) {
            x >>= 16;
            n += 8;
        }
        if (x >= 1 << 8) {
            x >>= 8;
            n += 4;
        }
        if (x >= 1 << 4) {
            x >>= 4;
            n += 2;
        }
        if (x >= 1 << 2) {
            x >>= 2;
            n += 1;
        }
    }
}
