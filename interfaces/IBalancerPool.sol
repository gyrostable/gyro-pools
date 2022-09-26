// SPDX-License-Identifier: GPL-3.0-or-later
pragma solidity 0.7.6;

interface IBalancerPool {
    function getPoolId() external view returns (bytes32);
}
