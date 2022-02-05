pragma solidity ^0.7.0;

import "@balancer-labs/v2-solidity-utils/contracts/math/FixedPoint.sol";
import "../../libraries/SignedFixedPoint.sol";
import "./GyroCEMMPoolErrors.sol";
import "@balancer-labs/v2-solidity-utils/contracts/math/Math.sol";
import "@balancer-labs/v2-solidity-utils/contracts/helpers/InputHelpers.sol";
import "@openzeppelin/contracts/utils/SafeCast.sol";

// solhint-disable private-vars-leading-underscore

/** @dev CEMM math library. Pretty much a direct translation of the python version (see `tests/`).
 * We use *signed* values here because some of the intermediate results can be negative (e.g. coordinates of points in
 * the untransformed circle, "prices" in the untransformed circle).
 */
library GyroCEMMMath {
    uint256 internal constant ONEHALF = 0.5e18;

    // TODO test what is needed or acceptable here. Dep/ on the source of c and
    // s, too. And if this should be checked in the contract at all.
    int256 internal constant VALIDATION_PRECISION_CS_NORM = 100; // 1e-16

    using SignedFixedPoint for int256;
    using FixedPoint for uint256;
    using SafeCast for uint256;
    using SafeCast for int256;
    // TODO replace manual calls

    // TODO decide if we wanna use underscores to mark internals or not. Also dep/ if we wanna do `using...for Params`.
    // TODO Copy comments and thm references from the python implementation.

    // Swap limits: amounts swapped may not be larger than this percentage of total balance.
    uint256 internal constant _MAX_IN_RATIO = 0.3e18;
    uint256 internal constant _MAX_OUT_RATIO = 0.3e18;

    // TODO SOMEDAY we may wanna make this storage for gas efficiency. Depends on how much we actually wanna store vs recompute.
    // TODO SOMEDAY we may wanna tune the width of these params; see PAMM
    // Note that all t values (not tp or tpp) could consist of uint's, as could all Params. But it's complicated to
    // convert all the time, so we make them all signed. We also store all intermediate values signed. An exception are
    // the functions that are used by the contract b/c there the values are stored unsigned.
    struct Params {
        // Price bounds (lower and upper). 0 < alpha < beta
        int256 alpha;
        int256 beta;
        // Rotation vector:
        // phi in (-90 degrees, 0] is the implicit rotation vector. It's stored as a point:
        int256 c; // c = cos(-phi) >= 0.
        int256 s; //  s = sin(-phi) >= 0.
        // Invariant: c^2 + s^2 == 1, i.e., the point (c, s) is normalized.

        // Stretching factor:
        int256 lambda; // lambda >= 1 where lambda == 1 is the circle.
    }

    function validateParams(Params memory params) internal pure {
        // Perhaps this should go into the GyroCEMMMath?
        // TODO test if we need alpha < 1 < beta
        _require(params.alpha > 0, GyroCEMMPoolErrors.PRICE_BOUNDS_WRONG);
        _require(params.beta > params.alpha, GyroCEMMPoolErrors.PRICE_BOUNDS_WRONG);
        _require(params.c >= 0, GyroCEMMPoolErrors.ROTATION_VECTOR_WRONG);
        _require(params.s >= 0, GyroCEMMPoolErrors.ROTATION_VECTOR_WRONG);

        int256 norm = params.c.mulDown(params.c);
        norm = norm.add(params.s.mulDown(params.s));
        _require(
            SignedFixedPoint.ONE - VALIDATION_PRECISION_CS_NORM <= norm &&
                norm <= SignedFixedPoint.ONE + VALIDATION_PRECISION_CS_NORM,
            GyroCEMMPoolErrors.ROTATION_VECTOR_NOT_NORMALIZED
        );
    }

    struct DerivedParams {
        // TODO SOMEDAY these could be cached. It's probably not worth it though. Could also be compressed so that only
        // the sqrt is stored.
        Vector2 tauAlpha;
        Vector2 tauBeta;
    }

    // TODO MAYBE make this just an array actually
    struct Vector2 {
        int256 x;
        int256 y;
    }

    // Scalar product of Vector2 objects
    function scalarProdUp(Vector2 memory t1, Vector2 memory t2) internal pure returns (int256 ret) {
        ret = t1.x.mulUp(t2.x).add(t1.y.mulUp(t2.y));
    }

    function scalarProdDown(Vector2 memory t1, Vector2 memory t2)
        internal
        pure
        returns (int256 ret)
    {
        ret = t1.x.mulDown(t2.x).add(t1.y.mulDown(t2.y));
    }

    // "Methods" for Params. We could put these into a separate library and import them via 'using' to get method call
    // syntax.

    /** @dev Calculate A^{-1}t where A^{-1} is given in Section 2.2
     *  This is rotating and scaling the circle into the ellipse */
    function mulAinv(Params memory params, Vector2 memory t)
        internal
        pure
        returns (Vector2 memory tp)
    {
        tp.x = params.c.mulDown(params.lambda).mulDown(t.x);
        tp.x = tp.x.add(params.s.mulDown(t.y));
        tp.y = (-params.s).mulDown(params.lambda).mulDown(t.x);
        tp.y = tp.y.add(params.c.mulDown(t.y));
    }

    /** @dev Calculate A t where A is given in Section 2.2
     *  This is reversing rotation and scaling of the ellipse (mapping back to circle) */
    function mulA(Params memory params, Vector2 memory tp)
        internal
        pure
        returns (Vector2 memory t)
    {
        t.x = params.c.divDown(params.lambda).mulDown(tp.x);
        t.x = t.x.sub(params.s.divDown(params.lambda).mulDown(tp.y));
        t.y = params.s.mulDown(tp.x);
        t.y = t.y.add(params.c.mulDown(tp.y));
    }

    /** @dev Given price px on the transformed ellipse, get the untransformed price pxc on the circle
     *  px = price of asset x in terms of asset y */
    function zeta(Params memory params, int256 px) internal pure returns (int256 pxc) {
        Vector2 memory nd = mulA(params, Vector2(-SignedFixedPoint.ONE, px));
        return -nd.y.divDown(nd.x);
    }

    /** @dev Given price px on the transformed ellipse, maps to the corresponding point on the untransformed normalized circle
     *  px = price of asset x in terms of asset y */
    function tau(Params memory params, int256 px) internal pure returns (Vector2 memory tpp) {
        return eta(zeta(params, px));
    }

    /** @dev Calculates tau in more efficient way if sqrt(1+zeta(px)^2) is known and input as second arg
     *  This sqrt can be calculated in liquidity updates using equation 7 in 2.1.7 Implementation
     *  w/o using a fractional power evaluation, which is when this tau function should be used */
    function tau(
        Params memory params,
        int256 px,
        int256 sqrt
    ) internal pure returns (Vector2 memory tpp) {
        return eta(zeta(params, px), sqrt);
    }

    // TODO this should only be computed once at deployment and stored as immutable
    function mkDerivedParams(Params memory params)
        internal
        pure
        returns (DerivedParams memory derived)
    {
        derived.tauAlpha = tau(params, params.alpha);
        derived.tauBeta = tau(params, params.beta);
    }

    /** @dev Given price on a circle, gives the normalized corresponding point on the circle centered at the origin
     *  pxc = price of asset x in terms of asset y (measured on the circle)
     *  Notice that the eta function does not depend on Params */
    function eta(int256 pxc) internal pure returns (Vector2 memory tpp) {
        int256 z = FixedPoint
            .powDown(FixedPoint.ONE.add(uint256(pxc.mulDown(pxc))), ONEHALF)
            .toInt256();
        tpp = eta(pxc, z);
    }

    /** @dev Calculates eta in more efficient way if the square root is known and input as second arg */
    function eta(int256 pxc, int256 z) internal pure returns (Vector2 memory tpp) {
        tpp.x = pxc.divDown(z);
        tpp.y = SignedFixedPoint.ONE.divDown(z);
    }

    /** @dev Calculate virtual offsets a and b.
     *   See calculation in Section 2.1.2 Computing reserve offsets
     *   Note that, in contrast to virtual reserve offsets in CPMM, these are *subtracted* from the real
     *  reserves, moving the curve to the upper-right. They can be positive or negative, but not both can be negative.
     */
    // TODO For gas efficiency, we may want to put these, up to the r factor, into DerivedParams.
    function virtualOffsets(
        Params memory params,
        DerivedParams memory derived,
        int256 invariant
    ) internal pure returns (Vector2 memory ab) {
        // TODO MAYBE gas optimization: Make specialized functions that only return the .x and .y components of
        // mulAinv(). We're throwing away half of that calculation right now.
        ab.x = invariant.mulDown(mulAinv(params, derived.tauBeta).x); // virtual offset a
        ab.y = invariant.mulDown(mulAinv(params, derived.tauAlpha).y); // virtual offset b
    }

    /** @dev Maximal values for the real reserves x and y when the respective other balance is 0, for a given
     *  invariant.
     *  See calculation in Section 2.1.2 Computing reserve offsets
     */
    function maxBalances(
        Params memory params,
        DerivedParams memory derived,
        int256 invariant
    ) internal pure returns (Vector2 memory xy) {
        Vector2 memory vecAinvTauBeta = mulAinv(params, derived.tauBeta);
        Vector2 memory vecAinvTauAlpha = mulAinv(params, derived.tauAlpha);

        // calculate offsets a,b. Reuses matrix calculations already done
        Vector2 memory ab;
        ab.x = invariant.mulDown(vecAinvTauBeta.x); // virtual offset a
        ab.y = invariant.mulDown(vecAinvTauAlpha.y); // virtual offset b

        xy.y = -invariant.mulDown(vecAinvTauBeta.y); // maximal y reserves
        xy.x = -invariant.mulDown(vecAinvTauAlpha.x); // maximal x reserves
        // shift maximal amounts by offsets
        xy.y = xy.y.add(ab.y);
        xy.x = xy.x.add(ab.x);
    }

    /** @dev Calculate normalized offsets chi = (a,b)/r without having computed the invariant r
     *   see Prop 8 in 2.1.3 Initialization from real reserves */
    function chi(Params memory params, DerivedParams memory derived)
        internal
        pure
        returns (Vector2 memory ret)
    {
        ret.x = mulAinv(params, derived.tauBeta).x;
        ret.y = mulAinv(params, derived.tauAlpha).y;
    }

    struct QParams {
        int256 a;
        int256 b;
        int256 c;
    }

    /** Solve quadratic equation for the 'plus sqrt' solution
     *  qparams contains a,b,c coefficients defining the quadratic.
     *  Reverts if the equation has no solution or is actually linear (i.e., a==0) */
    function solveQuadraticPlus(QParams memory qparams) internal pure returns (int256 x) {
        int256 sqrt = qparams.b.mulDown(qparams.b).sub(
            // TODO ONE.mulUp unnecessary?
            4 * SignedFixedPoint.ONE.mulUp(qparams.a).mulUp(qparams.c)
        );
        sqrt = FixedPoint.powDown(sqrt.toUint256(), ONEHALF).toInt256();
        x = (-qparams.b).add(sqrt).divDown(2 * SignedFixedPoint.ONE.mulUp(qparams.a));
    }

    /** Solve quadratic equation for the 'minus sqrt' solution
     *   qparams contains a,b,c coefficients defining the quadratic */
    function solveQuadraticMinus(QParams memory qparams) internal pure returns (int256 x) {
        int256 sqrt = qparams.b.mulDown(qparams.b).sub(
            4 * SignedFixedPoint.ONE.mulUp(qparams.a).mulUp(qparams.c)
        );
        sqrt = FixedPoint.powDown(sqrt.toUint256(), ONEHALF).toInt256();
        x = (-qparams.b).sub(sqrt).divDown(2 * SignedFixedPoint.ONE.mulUp(qparams.a));
    }

    /** @dev Compute the invariant 'r' corresponding to the given values. The invariant can't be negative, but
     *  we use a signed value to store it because all the other calculations are happening with signed ints,
     *  too.*/
    function calculateInvariant(
        uint256[] memory balances,
        Params memory params,
        DerivedParams memory derived
    ) internal pure returns (uint256 uinvariant) {
        Vector2 memory vbalances;
        vbalances.x = balances[0].toInt256();
        vbalances.y = balances[1].toInt256();
        return _calculateInvariant(vbalances, params, derived).toUint256();
    }

    /** @dev Computes the invariant r according to Prop 13 in 2.2.1 Initialization from Real Reserves */
    function _calculateInvariant(
        Vector2 memory balances,
        Params memory params,
        DerivedParams memory derived
    ) internal pure returns (int256 invariant) {
        Vector2 memory vecAt = mulA(params, balances);
        Vector2 memory vecAChi = mulA(params, chi(params, derived));
        QParams memory qparams;
        // Convert Prop 13 equation into quadratic coefficients, account for factors of 2 and minus signs
        // TODO (Steffen) Make sure a is never 0 (where the equation is linear). I think it's not, but double check!
        // (o/w the following call reverts with zero division)
        qparams.a = (scalarProdUp(vecAChi, vecAChi).sub(SignedFixedPoint.ONE)).divUp(
            2 * SignedFixedPoint.ONE
        );
        qparams.b = -scalarProdDown(vecAt, vecAChi);
        qparams.c = scalarProdUp(vecAt, vecAt).divUp(2 * SignedFixedPoint.ONE);
        invariant = solveQuadraticPlus(qparams);
    }

    /** @dev Instantanteous price.
     *  See Prop. 12 in 2.1.6 Computing Prices */
    function calculatePrice(
        uint256[] memory balances,
        Params memory params,
        DerivedParams memory derived,
        int256 invariant
    ) internal pure returns (uint256 px) {
        // shift by virtual offsets to get v(t)
        Vector2 memory ab = virtualOffsets(params, derived, invariant);
        Vector2 memory vec;
        vec.x = balances[0].toInt256().sub(ab.x);
        vec.y = balances[1].toInt256().sub(ab.y);

        // transform to circle to get Av(t)
        vec = mulA(params, vec);
        Vector2 memory pc;
        // compute prices on circle
        pc.x = vec.x.divDown(vec.y);
        pc.y = SignedFixedPoint.ONE;

        // Convert prices back to ellipse
        int256 pgx = scalarProdDown(pc, mulA(params, Vector2(SignedFixedPoint.ONE, 0)));
        pgx = pgx.divDown(scalarProdDown(pc, mulA(params, Vector2(0, SignedFixedPoint.ONE))));
        px = pgx.toUint256();
    }

    /** @dev Check that post-swap balances obey maximal asset bounds
     *  newBalance = post-swap balance of one asset
     *  assetIndex gives the index of the provided asset (0 = X, 1 = Y) */
    function checkAssetBounds(
        Params memory params,
        DerivedParams memory derived,
        int256 invariant,
        int256 newBalance,
        uint8 assetIndex
    ) internal pure {
        Vector2 memory xyPlus = maxBalances(params, derived, invariant);
        if (assetIndex == 0) {
            _require(newBalance < xyPlus.x, GyroCEMMPoolErrors.ASSET_BOUNDS_EXCEEDED);
        } else {
            _require(newBalance < xyPlus.y, GyroCEMMPoolErrors.ASSET_BOUNDS_EXCEEDED);
        }
    }

    function calcOutGivenIn(
        uint256[] memory balances,
        uint256 amountIn,
        bool tokenInIsToken0,
        Params memory params,
        DerivedParams memory derived,
        uint256 uinvariant
    ) internal pure returns (uint256 amountOut) {
        function(int256, Params memory, DerivedParams memory, int256)
            pure
            returns (int256) calcGiven;
        uint8 ixIn;
        uint8 ixOut;
        if (tokenInIsToken0) {
            ixIn = 0;
            ixOut = 1;
            calcGiven = calcYGivenX;
        } else {
            ixIn = 1;
            ixOut = 0;
            calcGiven = calcXGivenY;
        }

        _require(amountIn <= balances[ixIn].mulDown(_MAX_IN_RATIO), Errors.MAX_IN_RATIO);
        int256 balanceInNew = balances[ixIn].add(amountIn).toInt256();
        checkAssetBounds(params, derived, uinvariant.toInt256(), balanceInNew, ixIn);
        int256 balanceOutNew = calcGiven(balanceInNew, params, derived, uinvariant.toInt256());
        amountOut = balances[ixOut].sub(balanceOutNew.toUint256()); // calcGiven guarantees that this is safe.
        _require(amountOut <= balances[ixOut].mulDown(_MAX_OUT_RATIO), Errors.MAX_OUT_RATIO);
    }

    function calcInGivenOut(
        uint256[] memory balances,
        uint256 amountOut,
        bool tokenInIsToken0,
        Params memory params,
        DerivedParams memory derived,
        uint256 uinvariant
    ) internal pure returns (uint256 amountIn) {
        function(int256, Params memory, DerivedParams memory, int256)
            pure
            returns (int256) calcGiven;
        uint8 ixIn;
        uint8 ixOut;
        if (tokenInIsToken0) {
            ixIn = 0;
            ixOut = 1;
            calcGiven = calcXGivenY; // this reverses compared to calcOutGivenIn
        } else {
            ixIn = 1;
            ixOut = 0;
            calcGiven = calcYGivenX; // this reverses compared to calcOutGivenIn
        }

        _require(amountOut <= balances[ixOut].mulDown(_MAX_OUT_RATIO), Errors.MAX_OUT_RATIO);
        int256 balanceOutNew = balances[ixOut].sub(amountOut).toInt256();
        int256 balanceInNew = calcGiven(balanceOutNew, params, derived, uinvariant.toInt256());
        checkAssetBounds(params, derived, uinvariant.toInt256(), balanceInNew, ixIn);
        amountIn = balanceInNew.toUint256().sub(balances[ixIn]); // calcGiven guarantees that this is safe.
        _require(amountIn <= balances[ixIn].mulDown(_MAX_IN_RATIO), Errors.MAX_IN_RATIO);
    }

    /** @dev compute y such that (x, y) satisfy the invariant at the given parameters.
     *   See Prop 14 in section 2.2.2 Trade Execution */
    function calcYGivenX(
        int256 x,
        Params memory params,
        DerivedParams memory derived,
        int256 invariant
    ) internal pure returns (int256 y) {
        QParams memory qparams;
        Vector2 memory ab = virtualOffsets(params, derived, invariant);
        // shift by the virtual offsets
        x = x.sub(ab.x);
        int256 lamBar = SignedFixedPoint.ONE -
            SignedFixedPoint.ONE.divDown(params.lambda.mulDown(params.lambda));

        // Convert Prop 14 equation into quadratic coefficients, account for factors of 2 and minus signs
        qparams.a = (SignedFixedPoint.ONE.sub(lamBar.mulDown(params.s).mulDown(params.s))).divUp(
            2 * SignedFixedPoint.ONE
        );
        qparams.b = params.s.mulUp(params.c).mulUp(lamBar).mulUp(x);
        qparams.c = SignedFixedPoint.ONE.sub(lamBar.mulUp(params.c).mulUp(params.c));
        qparams.c = (qparams.c.mulDown(x).mulDown(x)).sub(invariant.mulDown(invariant));
        qparams.c = qparams.c.divUp(2 * SignedFixedPoint.ONE);

        y = solveQuadraticMinus(qparams);
        // shift back by the virtual offsets
        y = y.add(ab.y);
    }

    function calcXGivenY(
        int256 y,
        Params memory params,
        DerivedParams memory derived,
        int256 invariant
    ) internal pure returns (int256 x) {
        QParams memory qparams;
        Vector2 memory ab = virtualOffsets(params, derived, invariant);
        // shift by the virtual offsets
        y = y.sub(ab.y);
        int256 lamBar = SignedFixedPoint.ONE -
            SignedFixedPoint.ONE.divDown(params.lambda.mulDown(params.lambda));

        // Convert Prop 13 equation into quadratic coefficients, account for factors of 2 and minus signs
        qparams.a = (SignedFixedPoint.ONE.sub(lamBar.mulDown(params.c).mulDown(params.c))).divUp(
            2 * SignedFixedPoint.ONE
        );
        qparams.b = params.s.mulUp(params.c).mulUp(lamBar).mulUp(y);
        qparams.c = SignedFixedPoint.ONE.sub(lamBar.mulUp(params.s).mulUp(params.s));
        qparams.c = (qparams.c.mulDown(y).mulDown(y)).sub(invariant.mulDown(invariant));
        qparams.c = qparams.c.divUp(2 * SignedFixedPoint.ONE);

        x = solveQuadraticMinus(qparams);
        // shift back by the virtual offsets
        x = x.add(ab.x);
    }

    /** @dev calculate sqrt(1+zeta(px)^2) by taking advantage of Equation 7 in 2.1.7
     *  This can be used in liquidity updates to save gas */
    // SOMEDAY we might want to use the formula for the larger of the two balances to improve numerical accuracy.
    function calculateSqrtOnePlusZetaSquared(
        uint256[] memory balances,
        Params memory params,
        DerivedParams memory derived,
        int256 invariant
    ) internal pure returns (int256 sqrt) {
        Vector2 memory ab = virtualOffsets(params, derived, invariant);
        // shift by virtual offsets
        Vector2 memory vt;
        vt.x = balances[0].toInt256().sub(ab.x);
        vt.y = balances[1].toInt256().sub(ab.y);
        // transform by A
        vt = mulA(params, vt);
        // sqrt(1+zeta(px)^2) = - r / (Av(t).y). See Equation 7 in 2.1.7
        sqrt = - invariant.divUp(vt.y);
    }

    /** @dev If `deltaBalances` are such that, when changing `balances` by it, the price stays the same ("balanced
     * liquidity update"), then this returns the invariant after that change. This is more efficient than calling
     * `calculateInvariant()` on the updated balances. `isIncreaseLiq` denotes the sign of the update.
     */
    // TODO can't we just use ratios?! Like uinvariant * (balances[0] + deltaBalances[0])/balances[0]. Why wouldn't that work?!?
    function liquidityInvariantUpdate(
        uint256[] memory balances,
        Params memory params,
        DerivedParams memory derived,
        uint256 uinvariant,
        uint256[] memory deltaBalances,
        bool isIncreaseLiq
    ) internal pure returns (uint256 unewInvariant) {
        int256 px = calculatePrice(balances, params, derived, uinvariant.toInt256()).toInt256();
        int256 value = calculateSqrtOnePlusZetaSquared(
            balances,
            params,
            derived,
            uinvariant.toInt256()
        );
        Vector2 memory tauPx = tau(params, px, value);

        // deltaInv = (matrix calcs.x)/deltaX
        // repurpase 'value' variable to do the matrix calculations
        value = mulAinv(params, derived.tauBeta).x;
        value = value.sub(mulAinv(params, tauPx).x);

        // do the invariant update in uints
        uint256 uvalue = value >= 0 ? value.toUint256() : (-value).toUint256();
        uint256 deltaInv = uvalue.divDown(deltaBalances[0]);
        unewInvariant = isIncreaseLiq ? uinvariant.add(deltaInv) : uinvariant.sub(deltaInv);
    }

    // BPT Accounting. This is the same as for the CPMMv2 and CPMMv3.
    //
    // TODO LATER make a library for this, it's really about time.

    function _calcAllTokensInGivenExactBptOut(
        uint256[] memory balances,
        uint256 bptAmountOut,
        uint256 totalBPT
    ) internal pure returns (uint256[] memory) {
        /************************************************************************************
        // tokensInForExactBptOut                                                          //
        // (per token)                                                                     //
        // aI = amountIn (vec)             /   bptOut   \                                  //
        // b = balance (vec)     aI = b * | ------------ |                                 //
        // bptOut = bptAmountOut           \  totalBPT  /                                  //
        // bpt = totalBPT                                                                  //
        ************************************************************************************/

        // Tokens in, so we round up overall.
        uint256 bptRatio = bptAmountOut.divUp(totalBPT);

        uint256[] memory amountsIn = new uint256[](balances.length);
        for (uint256 i = 0; i < balances.length; i++) {
            amountsIn[i] = balances[i].mulUp(bptRatio);
        }

        return amountsIn;
    }

    function _calcTokensOutGivenExactBptIn(
        uint256[] memory balances,
        uint256 bptAmountIn,
        uint256 totalBPT
    ) internal pure returns (uint256[] memory) {
        /**********************************************************************************************
        // exactBPTInForTokensOut                                                                    //
        // (per token)                                                                               //
        // aO = amountOut                  /        bptIn         \                                  //
        // b = balance           a0 = b * | ---------------------  |                                 //
        // bptIn = bptAmountIn             \       totalBPT       /                                  //
        // bpt = totalBPT                                                                            //
        **********************************************************************************************/

        // Since we're computing an amount out, we round down overall. This means rounding down on both the
        // multiplication and division.

        uint256 bptRatio = bptAmountIn.divDown(totalBPT);

        uint256[] memory amountsOut = new uint256[](balances.length);
        for (uint256 i = 0; i < balances.length; i++) {
            amountsOut[i] = balances[i].mulDown(bptRatio);
        }

        return amountsOut;
    }

    // Protocol fees. This is - again - exactly equal to CPMMv2 and CPMMv3.
    // The caller needs to do a (safe) type conversion b/c we store our invariant signed, not unsigned.
    // TODO should also be a library

    /** @dev Calculates protocol fees due to Gyro and Balancer
     *   Note: we do this differently than normal Balancer pools by paying fees in BPT tokens
     *   b/c this is much more gas efficient than doing many transfers of underlying assets
     *   This function gets protocol fee parameters from GyroConfig
     */
    function _calcProtocolFees(
        uint256 previousInvariant,
        uint256 currentInvariant,
        uint256 currentBptSupply,
        uint256 protocolSwapFeePerc,
        uint256 protocolFeeGyroPortion
    ) internal pure returns (uint256, uint256) {
        /*********************************************************************************
        /*  Protocol fee collection should decrease the invariant L by
        *        Delta L = protocolSwapFeePerc * (currentInvariant - previousInvariant)
        *   To take these fees in BPT LP shares, the protocol mints Delta S new LP shares where
        *        Delta S = S * Delta L / ( currentInvariant - Delta L )
        *   where S = current BPT supply
        *   The protocol then splits the fees (in BPT) considering protocolFeeGyroPortion
        *   See also the write-up, Proposition 7.
        *********************************************************************************/

        if (currentInvariant <= previousInvariant) {
            // This shouldn't happen outside of rounding errors, but have this safeguard nonetheless to prevent the Pool
            // from entering a locked state in which joins and exits revert while computing accumulated swap fees.
            return (0, 0);
        }

        // Calculate due protocol fees in BPT terms
        // We round down to prevent issues in the Pool's accounting, even if it means paying slightly less in protocol
        // fees to the Vault.
        // For the numerator, we need to round down delta L. Also for the denominator b/c subtracted
        uint256 diffInvariant = protocolSwapFeePerc.mulDown(
            currentInvariant.sub(previousInvariant)
        );
        uint256 numerator = diffInvariant.mulDown(currentBptSupply);
        uint256 denominator = currentInvariant.sub(diffInvariant);
        uint256 deltaS = numerator.divDown(denominator);

        // Split fees between Gyro and Balancer
        uint256 gyroFees = protocolFeeGyroPortion.mulDown(deltaS);
        uint256 balancerFees = deltaS.sub(gyroFees);

        return (gyroFees, balancerFees);
    }
}
