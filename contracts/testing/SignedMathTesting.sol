// SPDX-License-Identifier: UNLICENSE

pragma solidity ^0.7.0;

import "../../libraries/SignedFixedPoint.sol";

contract SignedMathTesting {
    using SignedFixedPoint for int256;

    function add(int256 a, int256 b) external pure returns (int256) {
        return a.add(b);
    }

    function sub(int256 a, int256 b) external pure returns (int256) {
        return a.sub(b);
    }

    function mul(int256 a, int256 b) external pure returns (int256) {
        return a.mulDown(b);
    }

    function truediv(int256 a, int256 b) external pure returns (int256) {
        return a.divDown(b);
    }

    function addMag(int256 a, int256 b) external pure returns (int256) {
        return SignedFixedPoint.addMag(a, b);
    }

    function mulArrayUp(int256[] memory inputs) external pure returns (int256) {
        return SignedFixedPoint.mulArrayUp(inputs);
    }

    function mulArrayDown(int256[] memory inputs) external pure returns (int256) {
        return SignedFixedPoint.mulArrayDown(inputs);
    }

    function mulArray(int256[] memory inputs, bool roundUp) external pure returns (int256) {
        return SignedFixedPoint.mulArray(inputs, roundUp);
    }
}
