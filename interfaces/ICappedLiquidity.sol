// SPDX-License-Identifier: GPL-3.0-or-later
pragma solidity ^0.7.0;
pragma experimental ABIEncoderV2;

interface ICappedLiquidity {
    struct CapParams {
        bool capEnabled;
        uint120 perAddressCap;
        uint128 globalCap;
    }

    function setCapParams(CapParams memory params) external;

    function capParams() external view returns (CapParams memory);

    function capManager() external view returns (address);
}
