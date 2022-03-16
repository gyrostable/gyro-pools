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

    // Constants required for newton iteration method _squareRoot
    uint256 private constant SQRT_1E_NEG_1 = 316227766016837933;
    uint256 private constant SQRT_1E_NEG_3 = 31622776601683793;
    uint256 private constant SQRT_1E_NEG_5 = 3162277660168379;
    uint256 private constant SQRT_1E_NEG_7 = 316227766016837;
    uint256 private constant SQRT_1E_NEG_9 = 31622776601683;
    uint256 private constant SQRT_1E_NEG_11 = 3162277660168;
    uint256 private constant SQRT_1E_NEG_13 = 316227766016;
    uint256 private constant SQRT_1E_NEG_15 = 31622776601;
    uint256 private constant SQRT_1E_NEG_17 = 316227766;

    uint256 private constant MIN_NEWTON_STEP_SIZE = 5;

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
        // here a > 0, b < 0, and c < 0, which is a special case that works well w/o negative numbers
        // taking mb = -b and mc = -c:                            (1/2)
        //                                  mb + (mb^2 + 4 * a * mc)^                   //
        //                   L =    ------------------------------------------          //
        //                                          2 * a                               //
        //                                                                              //
        **********************************************************************************************/
        (uint256 a, uint256 mb, uint256 mc) = _calculateQuadraticTerms(
            balances,
            sqrtAlpha,
            sqrtBeta
        );
        return _calculateQuadratic(a, mb, mc);
    }

    /** @dev Prepares quadratic terms for input to _calculateQuadratic
     *   works with a special case of quadratic that works nicely w/o negative numbers
     *   assumes a > 0, b < 0, and c <= 0 and returns a, -b, -c
     */
    function _calculateQuadraticTerms(
        uint256[] memory balances,
        uint256 sqrtAlpha,
        uint256 sqrtBeta
    )
        internal
        pure
        returns (
            uint256 a,
            uint256 mb,
            uint256 mc
        )
    {
        a = FixedPoint.ONE.sub(sqrtAlpha.divDown(sqrtBeta));
        uint256 bterm0 = balances[1].divDown(sqrtBeta);
        uint256 bterm1 = balances[0].mulDown(sqrtAlpha);
        mb = bterm0.add(bterm1);
        mc = balances[0].mulDown(balances[1]);
    }

    /** @dev Calculates quadratic root for a special case of quadratic
     *   assumes a > 0, b < 0, and c <= 0, which is the case for a L^2 + b L + c = 0
     *   where   a = 1 - sqrt(alpha/beta)
     *           b = -(y/sqrt(beta) + x*sqrt(alpha))
     *           c = -x*y
     *   The special case works nicely w/o negative numbers.
     *   The args use the notation "mb" to represent -b, and "mc" to represent -c
     */
    function _calculateQuadratic(
        uint256 a,
        uint256 mb,
        uint256 mc
    ) internal pure returns (uint256 invariant) {
        uint256 denominator = a.mulDown(2 * FixedPoint.ONE);
        uint256 bSquare = mb.mulDown(mb);
        uint256 addTerm = a.mulDown(mc.mulDown(4 * FixedPoint.ONE));
        // The minus sign in the radicand cancels out in this special case, so we add
        uint256 radicand = bSquare.add(addTerm);
        uint256 sqrResult = _squareRoot(radicand, 5);
        // The minus sign in the numerator cancels out in this special case
        uint256 numerator = mb.add(sqrResult);
        invariant = numerator.divDown(denominator);
    }

    /** @dev Old sqrt function, replaced by Newton Iteration method below
     * function _squareRoot(uint256 input) internal pure returns (uint256 result) {
     *     result = input.powDown(FixedPoint.ONE / 2);
     * }
     */

    function _squareRoot(uint256 input, uint256 tolerance) internal pure returns (uint256) {
        if (input == 0) {
            return 0;
        }

        uint256 guess = _makeInitialGuess(input);

        // 7 iterations
        guess = (guess + ((input * FixedPoint.ONE) / guess)) / 2;
        guess = (guess + ((input * FixedPoint.ONE) / guess)) / 2;
        guess = (guess + ((input * FixedPoint.ONE) / guess)) / 2;
        guess = (guess + ((input * FixedPoint.ONE) / guess)) / 2;
        guess = (guess + ((input * FixedPoint.ONE) / guess)) / 2;
        guess = (guess + ((input * FixedPoint.ONE) / guess)) / 2;
        guess = (guess + ((input * FixedPoint.ONE) / guess)) / 2;

        // Check in given tolerance range
        uint256 guessSquared = guess.mulDown(guess);
        require(
            guessSquared <= input.add(guess.mulUp(tolerance)) &&
                guessSquared >= input.sub(guess.mulUp(tolerance)),
            "_sqrt FAILED"
        );

        return guess;
    }

    function _makeInitialGuess(uint256 input) internal pure returns (uint256) {
        if (input >= FixedPoint.ONE) {
            return (1 << (intLog2Halved(input / FixedPoint.ONE))) * FixedPoint.ONE;
        } else {
            if (input < 10) {
                return SQRT_1E_NEG_17;
            }
            if (input < 1e2) {
                return 1e10;
            }
            if (input < 1e3) {
                return SQRT_1E_NEG_15;
            }
            if (input < 1e4) {
                return 1e11;
            }
            if (input < 1e5) {
                return SQRT_1E_NEG_13;
            }
            if (input < 1e6) {
                return 1e12;
            }
            if (input < 1e7) {
                return SQRT_1E_NEG_11;
            }
            if (input < 1e8) {
                return 1e13;
            }
            if (input < 1e9) {
                return SQRT_1E_NEG_9;
            }
            if (input < 1e10) {
                return 1e14;
            }
            if (input < 1e11) {
                return SQRT_1E_NEG_7;
            }
            if (input < 1e12) {
                return 1e15;
            }
            if (input < 1e13) {
                return SQRT_1E_NEG_5;
            }
            if (input < 1e14) {
                return 1e16;
            }
            if (input < 1e15) {
                return SQRT_1E_NEG_3;
            }
            if (input < 1e16) {
                return 1e17;
            }
            if (input < 1e17) {
                return SQRT_1E_NEG_1;
            }
            return input;
        }
    }

    function intLog2Halved(uint256 x) internal pure returns (uint256 n) {
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

    /** @dev calculates change in invariant following an add or remove liquidity operation
     *   This assumes that the liquidity provided was correctly balanced.
     *   Using this instead of _calculateInvariant saves evaluating a square root
     */
    function _liquidityInvariantUpdate(
        uint256[] memory lastBalances,
        uint256 sqrtAlpha,
        uint256 sqrtBeta,
        uint256 lastInvariant,
        uint256[] memory deltaBalances,
        bool isIncreaseLiq
    ) internal pure returns (uint256 invariant) {
        /**********************************************************************************************
      // From Prop. 3 in Section 2.2.3 Liquidity Update                                            //
      // Assumed that the  liquidity provided is correctly balanced                                //
      // dL = change in L invariant, absolute value (sign information in isIncreaseLiq)            //
      // dY = change in Y reserves, absolute value (sign information in isIncreaseLiq)             //
      // sqrtPx = Square root of Price p_x              sqrtPx =  L / x'                           //
      // x' = virtual reserves X (real reserves + offsets)                                         //
      //                 /            dY            \       /            dX            \           //
      //          dL =  | -------------------------- |  =  | -------------------------- |          //
      //                 \  (sqrtPx - sqrtAlpha)    /       \ (1/sqrtPx - 1/sqrtBeta)  /           //
      // One of the denominators, but not both, can be 0. We dynamically choose the formula that   //
      // gives the best numerical stability.                                                       //
      **********************************************************************************************/
        uint256 virtualX = lastBalances[0] + lastInvariant.divUp(sqrtBeta);
        uint256 sqrtPx = _calculateSqrtPrice(lastInvariant, virtualX);
        uint256 diffInvariant;
        if (lastBalances[0] <= lastBalances[1]) {
            uint256 denominator = sqrtPx.sub(sqrtAlpha);
            diffInvariant = deltaBalances[1].divDown(denominator);
        } else {
            uint256 denominator = FixedPoint.ONE.divUp(sqrtPx).sub(
                FixedPoint.ONE.divDown(sqrtBeta)
            );
            diffInvariant = deltaBalances[0].divDown(denominator);
        }
        invariant = isIncreaseLiq
            ? lastInvariant.add(diffInvariant)
            : lastInvariant.sub(diffInvariant);
    }

    /** @dev Computes how many tokens can be taken out of a pool if `amountIn' are sent, given current balances
     *   balanceIn = existing balance of input token
     *   balanceOut = existing balance of requested output token
     *   virtualParamIn = virtual reserve offset for input token
     *   virtualParamOut = virtual reserve offset for output token
     *   Offsets are L/sqrt(beta) and L*sqrt(alpha) depending on what the `in' and `out' tokens are respectively
     *   Note signs are changed compared to Prop. 4 in Section 2.2.4 Trade (Swap) Exeuction to account for dy < 0
     */
    function _calcOutGivenIn(
        uint256 balanceIn,
        uint256 balanceOut,
        uint256 amountIn,
        uint256 virtualParamIn,
        uint256 virtualParamOut,
        uint256 currentInvariant
    ) internal pure returns (uint256 amountOut) {
        /**********************************************************************************************
      // Described for X = `in' asset and Y = `out' asset, but equivalent for the other case       //
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

        _require(amountIn <= balanceIn.mulDown(_MAX_IN_RATIO), Errors.MAX_IN_RATIO);
        uint256 virtIn = balanceIn.add(virtualParamIn);
        uint256 denominator = virtIn.add(amountIn);
        uint256 invSquare = currentInvariant.mulUp(currentInvariant);
        uint256 subtrahend = invSquare.divUp(denominator);
        uint256 virtOut = balanceOut.add(virtualParamOut);
        amountOut = virtOut.sub(subtrahend);

        // This in particular ensures amountOut < balanceOut.
        _require(amountOut <= balanceOut.mulDown(_MAX_OUT_RATIO), Errors.MAX_OUT_RATIO);
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
    ) internal pure returns (uint256 amountIn) {
        /**********************************************************************************************
      // dX = incrX  = amountIn  > 0                                                               //
      // dY = incrY  = amountOut < 0                                                               //
      // x = balanceIn             x' = x +  virtualParamX                                         //
      // y = balanceOut            y' = y +  virtualParamY                                         //
      // x = balanceIn                                                                             //
      // L  = inv.Liq                /              L^2             \                              //
      //                     dx =   |   --------------------------  |  -  x'                       //
      // x' = virtIn                \         ( y' + dy)           /                               //
      // y' = virtOut                                                                              //
      // Note that dy < 0 < dx.                                                                    //
      **********************************************************************************************/
        _require(amountOut <= balanceOut.mulDown(_MAX_OUT_RATIO), Errors.MAX_OUT_RATIO);
        uint256 virtOut = balanceOut.add(virtualParamOut);
        uint256 denominator = virtOut.sub(amountOut);
        uint256 invSquare = currentInvariant.mulUp(currentInvariant);
        uint256 term = invSquare.divUp(denominator);
        uint256 virtIn = balanceIn.add(virtualParamIn);
        amountIn = term.sub(virtIn);

        _require(amountIn <= balanceIn.mulDown(_MAX_IN_RATIO), Errors.MAX_IN_RATIO);
    }

    /** @dev calculate virtual offset a for reserves x, as in (x+a)*(y+b)=L^2
     */
    function _calculateVirtualParameter0(uint256 invariant, uint256 _sqrtBeta)
        internal
        pure
        returns (uint256)
    {
        return invariant.divDown(_sqrtBeta);
    }

    /** @dev calculate virtual offset b for reserves y, as in (x+a)*(y+b)=L^2
     */
    function _calculateVirtualParameter1(uint256 invariant, uint256 _sqrtAlpha)
        internal
        pure
        returns (uint256)
    {
        return invariant.mulDown(_sqrtAlpha);
    }

    /** @dev calculate square root price of asset X in terms of asset Y
     *   derived from relation p_x * (x+a)^2 = L^2
     */
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
