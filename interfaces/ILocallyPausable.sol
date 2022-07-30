// SPDX-License-Identifier: GPL-3.0-or-later
pragma solidity ^0.7.0;

interface ILocallyPausable {
    event Paused();
    event Unpaused();
    event PauseManagerChanged(address oldPauseManager, address newPauseManager);

    /// @notice Changes the account that is allow to pause a pool
    function changePauseManager(address _pauseManager) external;

    /// @notice Pauses the pool
    /// Can only be called by the pause manager
    function pause() external;

    /// @notice Unpauses the pool
    /// Can only be called by the pause manager
    function unpause() external;

    /// @return whether the pool is locally paused or not
    function isLocallyPaused() external view returns (bool);
}
