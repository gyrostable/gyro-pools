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

pragma solidity 0.7.6;

// solhint-disable

library GyroECLPPoolErrors {
    // Input
    uint256 internal constant ADDRESS_IS_ZERO_ADDRESS = 120;
    uint256 internal constant TOKEN_IN_IS_NOT_TOKEN_0 = 121;

    // Math
    uint256 internal constant PRICE_BOUNDS_WRONG = 354;
    uint256 internal constant ROTATION_VECTOR_WRONG = 355;
    uint256 internal constant ROTATION_VECTOR_NOT_NORMALIZED = 356;
    uint256 internal constant ASSET_BOUNDS_EXCEEDED = 357;
    uint256 internal constant DERIVED_TAU_NOT_NORMALIZED = 358;
    uint256 internal constant DERIVED_ZETA_WRONG = 359;
    uint256 internal constant STRETCHING_FACTOR_WRONG = 360;
    uint256 internal constant DERIVED_UVWZ_WRONG = 361;
    uint256 internal constant INVARIANT_DENOMINATOR_WRONG = 362;
    uint256 internal constant MAX_ASSETS_EXCEEDED = 363;
    uint256 internal constant MAX_INVARIANT_EXCEEDED = 363;
    uint256 internal constant DERIVED_DSQ_WRONG = 364;
}
