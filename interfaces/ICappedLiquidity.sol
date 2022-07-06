// SPDX-License-Identifier: GPL-3.0-or-later
pragma solidity ^0.7.0;

interface ICappedLiquidity {
    struct CapParams {
        bool capEnabled;
        uint120 perAddressCap;
        uint128 globalCap;
    }

    function capEnabled() external view returns (bool);

    function globalCap() external view returns (uint256);

    function perAddressCap() external view returns (uint256);
}
