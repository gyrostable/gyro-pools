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
import "@balancer-labs/v2-solidity-utils/contracts/helpers/BalancerErrors.sol";

/* solhint-disable private-vars-leading-underscore */

/// @dev Signed fixed point operations based on Balancer's FixedPoint library.
/// Note: The `{mul,div}{UpMag,DownMag}()` functions do *not* round up or down, respectively,
/// in a signed fashion (like ceil and floor operations), but *in absolute value* (or *magnitude*), i.e.,
/// towards 0. This is useful in some applications.
library SignedFixedPoint {
    int256 internal constant ONE = 1e18; // 18 decimal places
    // setting extra precision at 38 decimals, which is the most we can get w/o overflowing on normal multiplication
    // this allows 20 extra digits to absorb error when multiplying by large numbers
    int256 internal constant ONE_XP = 1e38; // 38 decimal places
    int256 internal constant MAX_POW_RELATIVE_ERROR = 10000; // 10^(-14)

    // Minimum base for the power function when the exponent is 'free' (larger than ONE).
    int256 internal constant MIN_POW_BASE_FREE_EXPONENT = 0.7e18;

    function add(int256 a, int256 b) internal pure returns (int256) {
        // Fixed Point addition is the same as regular checked addition

        int256 c = a + b;
        if (!(b >= 0 ? c >= a : c < a))
            _require(false, Errors.ADD_OVERFLOW);
        return c;
    }

    function addMag(int256 a, int256 b) internal pure returns (int256 c) {
        // add b in the same signed direction as a, i.e. increase the magnitude of a by b
        c = a > 0 ? add(a, b) : sub(a, b);
    }

    function sub(int256 a, int256 b) internal pure returns (int256) {
        // Fixed Point addition is the same as regular checked addition

        int256 c = a - b;
        if (!(b <= 0 ? c >= a : c < a))
            _require(false, Errors.SUB_OVERFLOW);
        return c;
    }

    /// @dev This rounds towards 0, i.e., down *in absolute value*!
    function mulDownMag(int256 a, int256 b) internal pure returns (int256) {
        int256 product = a * b;
        if (!(a == 0 || product / a == b))
            _require(false, Errors.MUL_OVERFLOW);

        return product / ONE;
    }

    /// @dev this implements mulDownMag w/o checking for over/under-flows, which saves significantly on gas if these aren't needed
    function mulDownMagU(int256 a, int256 b) internal pure returns (int256) {
        return (a * b) / ONE;
    }

    /// @dev This rounds away from 0, i.e., up *in absolute value*!
    function mulUpMag(int256 a, int256 b) internal pure returns (int256) {
        int256 product = a * b;
        if (!(a == 0 || product / a == b))
            _require(false, Errors.MUL_OVERFLOW);

        // If product > 0, the result should be ceil(p/ONE) = floor((p-1)/ONE) + 1, where floor() is implicit. If
        // product < 0, the result should be floor(p/ONE) = ceil((p+1)/ONE) - 1, where ceil() is implicit.
        // Addition for signed numbers: Case selection so we round away from 0, not always up.
        if (product > 0) return ((product - 1) / ONE) + 1;
        else if (product < 0) return ((product + 1) / ONE) - 1;
        // product == 0
        else return 0;
    }

    /// @dev this implements mulUpMag w/o checking for over/under-flows, which saves significantly on gas if these aren't needed
    function mulUpMagU(int256 a, int256 b) internal pure returns (int256) {
        int256 product = a * b;

        // If product > 0, the result should be ceil(p/ONE) = floor((p-1)/ONE) + 1, where floor() is implicit. If
        // product < 0, the result should be floor(p/ONE) = ceil((p+1)/ONE) - 1, where ceil() is implicit.
        // Addition for signed numbers: Case selection so we round away from 0, not always up.
        if (product > 0) return ((product - 1) / ONE) + 1;
        else if (product < 0) return ((product + 1) / ONE) - 1;
        // product == 0
        else return 0;
    }

    /// @dev Rounds towards 0, i.e., down in absolute value.
    function divDownMag(int256 a, int256 b) internal pure returns (int256) {
        if (b == 0)
            _require(false, Errors.ZERO_DIVISION);

        if (a == 0) {
            return 0;
        } else {
            int256 aInflated = a * ONE;
            if (aInflated / a != ONE)
                _require(false, Errors.DIV_INTERNAL);

            return aInflated / b;
        }
    }

    /// @dev this implements divDownMag w/o checking for over/under-flows, which saves significantly on gas if these aren't needed
    function divDownMagU(int256 a, int256 b) internal pure returns (int256) {
        if (b == 0)
            _require(false, Errors.ZERO_DIVISION);
        return (a * ONE) / b;
    }

    /// @dev Rounds away from 0, i.e., up in absolute value.
    function divUpMag(int256 a, int256 b) internal pure returns (int256) {
        if (b == 0)
            _require(false, Errors.ZERO_DIVISION);

        if (b < 0) {
            // Required so the below is correct.
            b = -b;
            a = -a;
        }

        if (a == 0) {
            return 0;
        } else {
            int256 aInflated = a * ONE;
            if (aInflated / a != ONE)
                _require(false, Errors.DIV_INTERNAL);

            if (aInflated > 0) return ((aInflated - 1) / b) + 1;
            else return ((aInflated + 1) / b) - 1;
        }
    }

    /// @dev this implements divUpMag w/o checking for over/under-flows, which saves significantly on gas if these aren't needed
    function divUpMagU(int256 a, int256 b) internal pure returns (int256) {
        if (b == 0)
            _require(false, Errors.ZERO_DIVISION);

        // TODO check if we can shave off some gas by logically refactoring this vs the below case distinction into one (on a * b or so).
        if (b < 0) {
            // Ensure b > 0 so the below is correct.
            b = -b;
            a = -a;
        }

        if (a == 0) {
            return 0;
        } else {
            if (a > 0) return ((a * ONE - 1) / b) + 1;
            else return ((a * ONE + 1) / b) - 1;
        }
    }

    /// @dev multiplies two extra precision numbers (with 38 decimals)
    /// rounds down in magnitude but this shouldn't matter
    /// multiplication can overflow if a,b are > 2 in magnitude
    function mulXp(int256 a, int256 b) internal pure returns (int256) {
        int256 product = a * b;
        if (!(a == 0 || product / a == b))
            _require(false, Errors.MUL_OVERFLOW);

        return product / ONE_XP;
    }

    /// @dev multiplies two extra precision numbers (with 38 decimals)
    /// rounds down in magnitude but this shouldn't matter
    /// multiplication can overflow if a,b are > 2 in magnitude
    /// this implements mulXp w/o checking for over/under-flows, which saves significantly on gas if these aren't needed
    function mulXpU(int256 a, int256 b) internal pure returns (int256) {
        return (a * b) / ONE_XP;
    }

    /// @dev divides two extra precision numbers (with 38 decimals)
    /// rounds down in magnitude but this shouldn't matter
    /// can overflow if a > 2 or b << 1 in magnitude
    function divXp(int256 a, int256 b) internal pure returns (int256) {
        if (b == 0)
            _require(false, Errors.ZERO_DIVISION);

        if (a == 0) {
            return 0;
        } else {
            int256 aInflated = a * ONE_XP;
            if (aInflated / a != ONE_XP)
                _require(false, Errors.DIV_INTERNAL);

            return aInflated / b;
        }
    }

    /// @dev divides two extra precision numbers (with 38 decimals)
    /// rounds down in magnitude but this shouldn't matter
    /// can overflow if a > 2 or b << 1 in magnitude
    /// this implements divXp w/o checking for over/under-flows, which saves significantly on gas if these aren't needed
    function divXpU(int256 a, int256 b) internal pure returns (int256) {
        if (b==0)
            _require(false, Errors.ZERO_DIVISION);

        return (a * ONE_XP) / b;
    }

    /// @dev multiplies normal precision a with extra precision b (with 38 decimals)
    /// Rounds down in signed direction
    /// returns normal precision of the product
    function mulDownXpToNp(int256 a, int256 b) internal pure returns (int256) {
        int256 b1 = b / 1e19;
        int256 b2 = b % 1e19;
        int256 prod1 = a * b1;
        if (!(a == 0 || prod1 / a == b1))
            _require(false, Errors.MUL_OVERFLOW);
        int256 prod2 = a * b2;
        if (!(a == 0 || prod2 / a == b2))
            _require(false, Errors.MUL_OVERFLOW);
        return prod1 >= 0 && prod2 >= 0 ? (prod1 + prod2 / 1e19) / 1e19 : (prod1 + prod2 / 1e19 + 1) / 1e19 - 1;
    }

    /// @dev multiplies normal precision a with extra precision b (with 38 decimals)
    /// Rounds down in signed direction
    /// returns normal precision of the product
    /// this implements mulDownXpToNp w/o checking for over/under-flows, which saves significantly on gas if these aren't needed
    function mulDownXpToNpU(int256 a, int256 b) internal pure returns (int256) {
        int256 b1 = b / 1e19;
        int256 b2 = b % 1e19;
        // TODO check if we eliminate these vars and save some gas (by only checking the sign of prod1, say)
        int256 prod1 = a * b1;
        int256 prod2 = a * b2;
        return prod1 >= 0 && prod2 >= 0 ? (prod1 + prod2 / 1e19) / 1e19 : (prod1 + prod2 / 1e19 + 1) / 1e19 - 1;
    }

    /// @dev multiplies normal precision a with extra precision b (with 38 decimals)
    /// Rounds up in signed direction
    /// returns normal precision of the product
    function mulUpXpToNp(int256 a, int256 b) internal pure returns (int256) {
        int256 b1 = b / 1e19;
        int256 b2 = b % 1e19;
        int256 prod1 = a * b1;
        if (!(a == 0 || prod1 / a == b1))
            _require(false, Errors.MUL_OVERFLOW);
        int256 prod2 = a * b2;
        if (!(a == 0 || prod2 / a == b2))
            _require(false, Errors.MUL_OVERFLOW);
        return prod1 <= 0 && prod2 <= 0 ? (prod1 + prod2 / 1e19) / 1e19 : (prod1 + prod2 / 1e19 - 1) / 1e19 + 1;
    }

    /// @dev multiplies normal precision a with extra precision b (with 38 decimals)
    /// Rounds up in signed direction
    /// returns normal precision of the product
    /// this implements mulUpXpToNp w/o checking for over/under-flows, which saves significantly on gas if these aren't needed
    function mulUpXpToNpU(int256 a, int256 b) internal pure returns (int256) {
        int256 b1 = b / 1e19;
        int256 b2 = b % 1e19;
        // TODO check if we eliminate these vars and save some gas (by only checking the sign of prod1, say)
        int256 prod1 = a * b1;
        int256 prod2 = a * b2;
        return prod1 <= 0 && prod2 <= 0 ? (prod1 + prod2 / 1e19) / 1e19 : (prod1 + prod2 / 1e19 - 1) / 1e19 + 1;
    }

    // TODO not implementing the pow functions right now b/c it's annoying and slightly ill-defined, and we prob don't need them.

    /**
     * @dev Returns x^y, assuming both are fixed point numbers, rounding down. The result is guaranteed to not be above
     * the true value (that is, the error function expected - actual is always positive).
     * x must be non-negative! y can be negative.
     */
    // function powDown(int256 x, int256 y) internal pure returns (int256) {
    //     _require(x >= 0, Errors.X_OUT_OF_BOUNDS);
    //     if (y > 0) {
    //         uint256 uret = FixedPoint.powDown(uint256(x), uint256(y));
    //     } else {
    //         // TODO does this cost a lot of precision compared to a direct implementation (which we don't have)?
    //         return ONE.divDown(FixedPoint.powUp(uint256(x), uint256(-y)));
    //     }
    // }

    /**
     * @dev Returns x^y, assuming both are fixed point numbers, rounding up. The result is guaranteed to not be below
     * the true value (that is, the error function expected - actual is always negative).
     * x must be non-negative! y can be negative.
     */
    // function powUp(int256 x, int256 y) internal pure returns (int256) {
    //     _require(x >= 0, Errors.X_OUT_OF_BOUNDS);
    //     if (y > 0)
    //         return FixedPoint.powUp(x, y);
    //     else
    //         // TODO does this cost a lot of precision compared to a direct implementation (which we don't have)?
    //         return ONE.divUp(FixedPoint.powDown(x, -y));
    // }

    /**
     * @dev Returns the complement of a value (1 - x), capped to 0 if x is larger than 1.
     *
     * Useful when computing the complement for values with some level of relative error, as it strips this error and
     * prevents intermediate negative values.
     */
    function complement(int256 x) internal pure returns (int256) {
        if (x >= ONE || x <= 0) return 0;
        return ONE - x;
    }
}
