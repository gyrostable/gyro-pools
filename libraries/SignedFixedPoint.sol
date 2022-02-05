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
library SignedFixedPoint {
    int256 internal constant ONE = 1e18; // 18 decimal places
    int256 internal constant MAX_POW_RELATIVE_ERROR = 10000; // 10^(-14)

    // Minimum base for the power function when the exponent is 'free' (larger than ONE).
    int256 internal constant MIN_POW_BASE_FREE_EXPONENT = 0.7e18;

    function add(int256 a, int256 b) internal pure returns (int256) {
        // Fixed Point addition is the same as regular checked addition

        int256 c = a + b;
        _require(b >= 0 ? c >= a : c < a, Errors.ADD_OVERFLOW);
        return c;
    }

    function sub(int256 a, int256 b) internal pure returns (int256) {
        // Fixed Point addition is the same as regular checked addition

        int256 c = a - b;
        _require(b <= 0 ? c >= a : c < a, Errors.SUB_OVERFLOW);
        return c;
    }

    // TODO do we also want the other two rounding directions (+ 4 functions then)? Do we want it instead?

    /// @dev This rounds towards 0, i.e., down *in absolute value*!
    function mulDown(int256 a, int256 b) internal pure returns (int256) {
        int256 product = a * b;
        _require(a == 0 || product / a == b, Errors.MUL_OVERFLOW);

        return product / ONE;
    }

    /// @dev This rounds away from 0, i.e., up *in absolute value*!
    function mulUp(int256 a, int256 b) internal pure returns (int256) {
        int256 product = a * b;
        _require(a == 0 || product / a == b, Errors.MUL_OVERFLOW);

        // If product > 0, the result should be ceil(p/ONE) = floor((p-1)/ONE) + 1, where floor() is implicit. If
        // product < 0, the result should be floor(p/ONE) = ceil((p+1)/ONE) - 1, where ceil() is implicit.
        // Addition for signed numbers: Case selection so we round away from 0, not always up.
        if (product > 0)
            return ((product - 1) / ONE) + 1;
        else if (product < 0)
            return ((product + 1) / ONE) - 1;
        else  // product == 0
            return 0;
    }

    /// @dev Rounds towards 0, i.e., down in absolute value.
    function divDown(int256 a, int256 b) internal pure returns (int256) {
        _require(b != 0, Errors.ZERO_DIVISION);

        if (a == 0) {
            return 0;
        } else {
            int256 aInflated = a * ONE;
            _require(aInflated / a == ONE, Errors.DIV_INTERNAL); // mul overflow

            return aInflated / b;
        }
    }

    /// @dev Rounds away from 0, i.e., up in absolute value.
    function divUp(int256 a, int256 b) internal pure returns (int256) {
        _require(b != 0, Errors.ZERO_DIVISION);

        if (a == 0) {
            return 0;
        } else {
            int256 aInflated = a * ONE;
            _require(aInflated / a == ONE, Errors.DIV_INTERNAL); // mul overflow

            if (aInflated > 0)
                return ((aInflated - 1) / b) + 1;
            else
                return ((aInflated + 1) / b) - 1;
        }
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
        if (x >= ONE || x <= 0)
            return 0;
        return ONE - x;
    }
}
