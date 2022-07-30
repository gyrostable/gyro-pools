// SPDX-License-Identifier: GPL-3.0-or-later
pragma solidity ^0.7.0;

import "../interfaces/ILocallyPausable.sol";

/**
 * @notice This contract is used to allow a pool to be paused directly
 */
contract LocallyPausable is ILocallyPausable {
    address public pauseManager;

    bool internal _locallyPaused;

    string internal constant _NOT_PAUSE_MANAGER = "not pause manager";
    string internal constant _PAUSED = "pool is locally paused";

    modifier whenNotLocallyPaused() {
        require(!_locallyPaused, _PAUSED);
        _;
    }

    constructor(address _pauseManager) {
        pauseManager = _pauseManager;
    }

    /// @inheritdoc ILocallyPausable
    function changePauseManager(address _pauseManager) external override {
        address currentPauseManager = pauseManager;
        require(currentPauseManager == msg.sender, _NOT_PAUSE_MANAGER);
        pauseManager = _pauseManager;
        emit PauseManagerChanged(currentPauseManager, _pauseManager);
    }

    /// @inheritdoc ILocallyPausable
    function pause() external override {
        require(pauseManager == msg.sender, _NOT_PAUSE_MANAGER);
        _locallyPaused = true;
        emit Paused();
    }

    /// @inheritdoc ILocallyPausable
    function unpause() external override {
        require(pauseManager == msg.sender, _NOT_PAUSE_MANAGER);
        _locallyPaused = false;
        emit Unpaused();
    }

    /// @inheritdoc ILocallyPausable
    function isLocallyPaused() external view override returns (bool) {
        return _locallyPaused;
    }
}
