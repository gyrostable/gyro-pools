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
pragma experimental ABIEncoderV2;

import "./ExtensibleBaseWeightedPool.sol";
import "./GyroThreeMath.sol";

/**
 * @dev Gyro Three Pool with immutable weights.
 */
contract GyroThreePool is ExtensibleBaseWeightedPool {
    using FixedPoint for uint256;

    uint256 private _root3Alpha;

    uint256 private constant _MAX_TOKENS = 3;

    IERC20 internal immutable _token0;
    IERC20 internal immutable _token1;
    IERC20 internal immutable _token2;

    // All token balances are normalized to behave as if the token had 18 decimals. We assume a token's decimals will
    // not change throughout its lifetime, and store the corresponding scaling factor for each at construction time.
    // These factors are always greater than or equal to one: tokens with more than 18 decimals are not supported.
    uint256 internal immutable _scalingFactor0;
    uint256 internal immutable _scalingFactor1;
    uint256 internal immutable _scalingFactor2;

    constructor(
        IVault vault,
        string memory name,
        string memory symbol,
        IERC20[] memory tokens,
        uint256 root3Alpha,
        address[] memory assetManagers,
        uint256 swapFeePercentage,
        uint256 pauseWindowDuration,
        uint256 bufferPeriodDuration,
        address owner
    )
        ExtensibleBaseWeightedPool(
            vault,
            name,
            symbol,
            tokens,
            assetManagers,
            swapFeePercentage,
            pauseWindowDuration,
            bufferPeriodDuration,
            owner
        )
    {
        require(tokens.length == 3);

        _token0 = tokens[0];
        _token1 = tokens[1];
        _token2 = tokens[2];

        _scalingFactor0 = _computeScalingFactor(tokens[0]);
        _scalingFactor1 = _computeScalingFactor(tokens[1]);
        _scalingFactor2 = _computeScalingFactor(tokens[2]);

        // TODO maybe put a stricter bound here, like 0.9999
        require(root3Alpha < 1, GyroThreePoolErrors.PRICE_BOUNDS_WRONG);
        _root3Alpha = root3Alpha;
    }

    // We don't support weights at the moment; in other words, all tokens are always weighted equally and thus their
    // normalized weights are all 1/3. This is what the functions return.

    function _getNormalizedWeight(IERC20 token)
        internal
        view
        virtual
        override
        returns (uint256)
    {
        return FixedPoint.ONE/3;
    }

    function _getNormalizedWeights()
        internal
        view
        virtual
        override
        returns (uint256[] memory)
    {
        uint256[] memory normalizedWeights = new uint256[](3);

        // prettier-ignore
        {
            normalizedWeights[0] = FixedPoint.ONE/3;
            normalizedWeights[1] = FixedPoint.ONE/3;
            normalizedWeights[2] = FixedPoint.ONE/3;
        }

        return normalizedWeights;
    }

    /// @dev Since all weights are always the same, the max-weight token is arbitrary. We return token 0.
    function _getNormalizedWeightsAndMaxWeightIndex()
        internal
        view
        virtual
        override
        returns (uint256[] memory, uint256)
    {
        return (_getNormalizedWeights(), 0);
    }

    function _getMaxTokens() internal pure virtual override returns (uint256) {
        return _MAX_TOKENS;
    }

    function _getTotalTokens()
        internal
        view
        virtual
        override
        returns (uint256)
    {
        return 3;
    }

    /**
     * @dev Returns the scaling factor for one of the Pool's tokens. Reverts if `token` is not a token registered by the
     * Pool.
     */
    function _scalingFactor(IERC20 token)
        internal
        view
        virtual
        override
        returns (uint256)
    {
        // prettier-ignore
        if (token == _token0) { return _scalingFactor0; }
        else if (token == _token1) { return _scalingFactor1; }
        else if (token == _token2) { return _scalingFactor2; }
        else {
            _revert(Errors.INVALID_TOKEN);
        }
    }

    function _scalingFactors()
        internal
        view
        virtual
        override
        returns (uint256[] memory)
    {
        uint256 totalTokens = _getTotalTokens();
        uint256[] memory scalingFactors = new uint256[](totalTokens);

        // prettier-ignore
        {
            scalingFactors[0] = _scalingFactor0;
            scalingFactors[1] = _scalingFactor1;
            scalingFactors[2] = _scalingFactor2;
        }

        return scalingFactors;
    }

    function _onSwapGivenIn(
        SwapRequest memory swapRequest,
        uint256 currentBalanceTokenIn,
        uint256 currentBalanceTokenOut
    ) internal view virtual override whenNotPaused returns (uint256) {
        (uint256 currentInvariant, uint256 virtualOffset) = _calculateCurrentValues();
        // todo maybe improve gas: These could be uint8.
        uint256 tokenIndexIn = _tokenAddressToIndex(swapRequest.tokenIn);
        uint256 tokenIndexOut = _tokenAddressToIndex(swapRequest.tokenOut);
        return _onSwapGivenIn(swapRequest, balances, tokenIndexIn, tokenIndexOut, virtualOffset, currentInvariant);
    }

    /* @dev This function originally comes from 'BaseMinimialSawpInfoPool' and was introduced in the context of
    /* explicit fee processing. We don't process fees in this pool, but we still need this method for other reasons.
     */
    function _tokenAddressToIndex(IERC20 token) internal view virtual override returns (uint256) {
        if (token == _token0)
            return 0;
        if (token == _token1)
            return 1;
        if (token == _token2)
            return 2;
        _revert(Errors.INVALID_TOKEN);
    }

    function _calculateCurrentValues() private view returns (uint256 invariant, uint256 virtualOffset) {
        (, uint256[] memory balances, ) = getVault().getPoolTokens(getPoolId());
        invariant = GyroThreeMath._calculateInvariant(balances, alpha3root);
        virtualOffset = _root3Alpha.mulDown(invariant);
    }


    function _onSwapGivenIn(
        SwapRequest memory swapRequest,
        uint256[] memory balances,
        uint256 currentBalanceTokenIn,
        uint256 currentBalanceTokenOut,
        uint256 virtualParamIn,
        uint256 virtualParamOut,
        uint256 invariant
    ) private pure returns (uint256) {
        // Swaps are disabled while the contract is paused.
        return
            GyroThreeMath._calcOutGivenIn(
                currentBalanceTokenIn,
                currentBalanceTokenOut,
                swapRequest.amount,
                virtualParamIn,
                virtualParamOut,
                invariant
            );
    }

    function _onSwapGivenOut(
        SwapRequest memory swapRequest,
        uint256 currentBalanceTokenIn,
        uint256 currentBalanceTokenOut,
        uint256 virtualParamIn,
        uint256 virtualParamOut,
        uint256 invariant
    ) private pure returns (uint256) {
        // Swaps are disabled while the contract is paused.
        return
            GyroThreeMath._calcInGivenOut(
                currentBalanceTokenIn,
                currentBalanceTokenOut,
                swapRequest.amount,
                virtualParamIn,
                virtualParamOut,
                invariant
            );
    }

    /**
     * @dev Called when the Pool is joined for the first time; that is, when the BPT total supply is zero.
     *
     * Returns the amount of BPT to mint, and the token amounts the Pool will receive in return.
     *
     * Minted BPT will be sent to `recipient`, except for _MINIMUM_BPT, which will be deducted from this amount and sent
     * to the zero address instead. This will cause that BPT to remain forever locked there, preventing total BTP from
     * ever dropping below that value, and ensuring `_onInitializePool` can only be called once in the entire Pool's
     * lifetime.
     *
     * The tokens granted to the Pool will be transferred from `sender`. These amounts are considered upscaled and will
     * be downscaled (rounding up) before being returned to the Vault.
     */
    function _onInitializePool(
        bytes32,
        address,
        address,
        bytes memory userData
    ) internal override returns (uint256, uint256[] memory) {
        ExtensibleBaseWeightedPool.JoinKind kind = userData.joinKind();
        _require(
            kind == ExtensibleBaseWeightedPool.JoinKind.INIT,
            Errors.UNINITIALIZED
        );

        uint256[] memory amountsIn = userData.initialAmountsIn();
        InputHelpers.ensureInputLengthMatch(amountsIn.length, 2);
        _upscaleArray(amountsIn);

        // uint256[] memory sqrtParams = _sqrtParameters();

        uint256 invariantAfterJoin = GyroThreeMath._calculateInvariant(
            amountsIn,
            sqrtParams[0],
            sqrtParams[1]
        );

        // Set the initial BPT to the value of the invariant times the number of tokens. This makes BPT supply more
        // consistent in Pools with similar compositions but different number of tokens.

        uint256 bptAmountOut = Math.mul(invariantAfterJoin, 2);

        _lastInvariant = invariantAfterJoin;

        return (bptAmountOut, amountsIn);
    }

    /**
     * @dev Called whenever the Pool is joined after the first initialization join (see `_onInitializePool`).
     *
     * Returns the amount of BPT to mint, the token amounts that the Pool will receive in return, and the number of
     * tokens to pay in protocol swap fees.
     *
     * Implementations of this function might choose to mutate the `balances` array to save gas (e.g. when
     * performing intermediate calculations, such as subtraction of due protocol fees). This can be done safely.
     *
     * Minted BPT will be sent to `recipient`.
     *
     * The tokens granted to the Pool will be transferred from `sender`. These amounts are considered upscaled and will
     * be downscaled (rounding up) before being returned to the Vault.
     *
     * Due protocol swap fees will be taken from the Pool's balance in the Vault (see `IBasePool.onJoinPool`). These
     * amounts are considered upscaled and will be downscaled (rounding down) before being returned to the Vault.
     */
    function _onJoinPool(
        bytes32,
        address,
        address,
        uint256[] memory balances,
        uint256,
        uint256 protocolSwapFeePercentage,
        bytes memory userData
    )
        internal
        override
        returns (
            uint256,
            uint256[] memory,
            uint256[] memory
        )
    {
        uint256[] memory normalizedWeights = _normalizedWeights();

        // Due protocol swap fee amounts are computed by measuring the growth of the invariant between the previous join
        // or exit event and now - the invariant's growth is due exclusively to swap fees. This avoids spending gas
        // computing them on each individual swap

        uint256[] memory sqrtParams = _sqrtParameters();
        uint256 lastInvariant = _lastInvariant;

        uint256 invariantBeforeJoin = GyroThreeMath._calculateInvariant(
            balances,
            sqrtParams[0],
            sqrtParams[1]
        );

        uint256[] memory dueProtocolFeeAmounts = _getDueProtocolFeeAmounts(
            balances,
            normalizedWeights,
            lastInvariant,
            invariantBeforeJoin,
            protocolSwapFeePercentage
        );

        // Update current balances by subtracting the protocol fee amounts
        _mutateAmounts(balances, dueProtocolFeeAmounts, FixedPoint.sub);
        (uint256 bptAmountOut, uint256[] memory amountsIn) = _doJoin(
            balances,
            userData
        );

        // We have the incrementX (amountIn) and balances (excluding fees) so we should be able to calculate incrementL
        _lastInvariant = GyroThreeMath._liquidityInvariantUpdate(
            balances,
            sqrtParams[0],
            sqrtParams[1],
            lastInvariant,
            amountsIn[1],
            true
        );

        return (bptAmountOut, amountsIn, dueProtocolFeeAmounts);
    }

    /**
     * @dev Called whenever the Pool is exited.
     *
     * Returns the amount of BPT to burn, the token amounts for each Pool token that the Pool will grant in return, and
     * the number of tokens to pay in protocol swap fees.
     *
     * Implementations of this function might choose to mutate the `balances` array to save gas (e.g. when
     * performing intermediate calculations, such as subtraction of due protocol fees). This can be done safely.
     *
     * BPT will be burnt from `sender`.
     *
     * The Pool will grant tokens to `recipient`. These amounts are considered upscaled and will be downscaled
     * (rounding down) before being returned to the Vault.
     *
     * Due protocol swap fees will be taken from the Pool's balance in the Vault (see `IBasePool.onExitPool`). These
     * amounts are considered upscaled and will be downscaled (rounding down) before being returned to the Vault.
     */
    function _onExitPool(
        bytes32,
        address,
        address,
        uint256[] memory balances,
        uint256 lastChangeBlock,
        uint256 protocolSwapFeePercentage,
        bytes memory userData
    )
        internal
        override
        returns (
            uint256 bptAmountIn,
            uint256[] memory amountsOut,
            uint256[] memory dueProtocolFeeAmounts
        )
    {
        // Exits are not completely disabled while the contract is paused: proportional exits (exact BPT in for tokens
        // out) remain functional.

        uint256[] memory normalizedWeights = _normalizedWeights();

        uint256[] memory sqrtParams = _sqrtParameters();
        uint256 lastInvariant = _lastInvariant;

        if (_isNotPaused()) {
            // Update price oracle with the pre-exit balances
            _updateOracle(lastChangeBlock, balances[0], balances[1]);

            // Due protocol swap fee amounts are computed by measuring the growth of the invariant between the previous
            // join or exit event and now - the invariant's growth is due exclusively to swap fees. This avoids
            // spending gas calculating the fees on each individual swap.
            // TO DO: Same here as in joinPool
            uint256 invariantBeforeExit = GyroThreeMath._calculateInvariant(
                balances,
                sqrtParams[0],
                sqrtParams[1]
            );
            dueProtocolFeeAmounts = _getDueProtocolFeeAmounts(
                balances,
                normalizedWeights,
                lastInvariant,
                invariantBeforeExit,
                protocolSwapFeePercentage
            );

            // Update current balances by subtracting the protocol fee amounts
            _mutateAmounts(balances, dueProtocolFeeAmounts, FixedPoint.sub);
        } else {
            // If the contract is paused, swap protocol fee amounts are not charged and the oracle is not updated
            // to avoid extra calculations and reduce the potential for errors.
            dueProtocolFeeAmounts = new uint256[](2);
        }

        (bptAmountIn, amountsOut) = _doExit(balances, userData);

        _lastInvariant = GyroThreeMath._liquidityInvariantUpdate(
            balances,
            sqrtParams[0],
            sqrtParams[1],
            lastInvariant,
            amountsOut[1],
            false
        );

        return (bptAmountIn, amountsOut, dueProtocolFeeAmounts);
    }

    /**
     * @dev Returns the current value of the invariant.
     */
    function getInvariant() public view override returns (uint256) {
        (, uint256[] memory balances, ) = getVault().getPoolTokens(getPoolId());
        uint256[] memory sqrtParams = _sqrtParameters();

        // Since the Pool hooks always work with upscaled balances, we manually
        // upscale here for consistency
        _upscaleArray(balances);

        return
            GyroThreeMath._calculateInvariant(
                balances,
                sqrtParams[0],
                sqrtParams[1]
            );
    }

    function _calculateCurrentValues(
        uint256 balanceTokenIn,
        uint256 balanceTokenOut,
        bool tokenInIsToken0
    )
        internal
        view
        returns (
            uint256 currentInvariant,
            uint256 virtualParamIn,
            uint256 virtualParamOut
        )
    {
        // if we have more tokens we might need to get the balances from the Vault
        uint256[] memory balances = new uint256[](2);
        balances[0] = tokenInIsToken0 ? balanceTokenIn : balanceTokenOut;
        balances[1] = tokenInIsToken0 ? balanceTokenOut : balanceTokenIn;

        uint256[] memory sqrtParams = _sqrtParameters();

        currentInvariant = GyroThreeMath._calculateInvariant(
            balances,
            sqrtParams[0],
            sqrtParams[1]
        );

        uint256[] memory virtualParam = new uint256[](2);
        virtualParam = GyroThreePool._getVirtualParameters(
            sqrtParams,
            currentInvariant
        );

        virtualParamIn = tokenInIsToken0 ? virtualParam[0] : virtualParam[1];
        virtualParamOut = tokenInIsToken0 ? virtualParam[1] : virtualParam[0];
    }

    function _joinAllTokensInForExactBPTOut(
        uint256[] memory balances,
        bytes memory userData
    ) internal view override returns (uint256, uint256[] memory) {
        uint256 bptAmountOut = userData.allTokensInForExactBptOut();
        // Note that there is no maximum amountsIn parameter: this is handled by `IVault.joinPool`.

        uint256[] memory amountsIn = GyroThreeMath
            ._calcAllTokensInGivenExactBptOut(
                balances,
                bptAmountOut,
                totalSupply()
            );

        return (bptAmountOut, amountsIn);
    }

    function _exitExactBPTInForTokensOut(
        uint256[] memory balances,
        bytes memory userData
    ) internal view override returns (uint256, uint256[] memory) {
        // This exit function is the only one that is not disabled if the contract is paused: it remains unrestricted
        // in an attempt to provide users with a mechanism to retrieve their tokens in case of an emergency.
        // This particular exit function is the only one that remains available because it is the simplest one, and
        // therefore the one with the lowest likelihood of errors.

        uint256 bptAmountIn = userData.exactBptInForTokensOut();
        // Note that there is no minimum amountOut parameter: this is handled by `IVault.exitPool`.

        uint256[] memory amountsOut = GyroThreeMath
            ._calcTokensOutGivenExactBptIn(
                balances,
                bptAmountIn,
                totalSupply()
            );
        return (bptAmountIn, amountsOut);
    }

    // Helpers

    function _getDueProtocolFeeAmounts(
        uint256[] memory balances,
        uint256[] memory normalizedWeights,
        uint256 previousInvariant,
        uint256 currentInvariant,
        uint256 protocolSwapFeePercentage
    ) internal view override returns (uint256[] memory) {
        // Initialize with zeros
        uint256[] memory dueProtocolFeeAmounts = new uint256[](2);

        // Early return if the protocol swap fee percentage is zero, saving gas.
        if (protocolSwapFeePercentage == 0) {
            return dueProtocolFeeAmounts;
        }

        // The protocol swap fees are always paid using the token with the largest weight in the Pool. As this is the
        // token that is expected to have the largest balance, using it to pay fees should not unbalance the Pool.
        dueProtocolFeeAmounts[_maxWeightTokenIndex] = GyroThreeMath
            ._calcDueTokenProtocolSwapFeeAmount(
                balances[_maxWeightTokenIndex],
                normalizedWeights[_maxWeightTokenIndex],
                previousInvariant,
                currentInvariant,
                protocolSwapFeePercentage
            );

        return dueProtocolFeeAmounts;
    }
}
