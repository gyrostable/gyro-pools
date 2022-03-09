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
    int256 internal constant ONE = 1e18; // 18 decimal places

    int256 internal constant VALIDATION_PRECISION_NORMED_INPUT = 500; // 5e-16
    int256 internal constant VALIDATION_PRECISION_ZETA = 500; // 5e-16

    using SignedFixedPoint for int256;
    using FixedPoint for uint256;
    using SafeCast for uint256;
    using SafeCast for int256;

    // Swap limits: amounts swapped may not be larger than this percentage of total balance.
    uint256 internal constant _MAX_IN_RATIO = 0.3e18;
    uint256 internal constant _MAX_OUT_RATIO = 0.3e18;
    uint256 internal constant _MIN_BAL_RATIO = 1e13; // 1e-5

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
        _require(params.alpha > 0, GyroCEMMPoolErrors.PRICE_BOUNDS_WRONG);
        _require(params.beta > params.alpha, GyroCEMMPoolErrors.PRICE_BOUNDS_WRONG);
        _require(params.c >= 0, GyroCEMMPoolErrors.ROTATION_VECTOR_WRONG);
        _require(params.s >= 0, GyroCEMMPoolErrors.ROTATION_VECTOR_WRONG);
        _require(params.lambda >= 1, GyroCEMMPoolErrors.STRETCHING_FACTOR_WRONG);
        // lambda assumed to only have 3 significant decimal digits (0s after)
        _require((params.lambda / 1e15) * 1e15 == params.lambda, GyroCEMMPoolErrors.STRETCHING_FACTOR_WRONG);
        validateNormed(Vector2(params.c, params.s), GyroCEMMPoolErrors.ROTATION_VECTOR_NOT_NORMALIZED);
    }

    struct DerivedParams {
        Vector2 tauAlpha;
        Vector2 tauBeta;
    }

    struct Vector2 {
        int256 x;
        int256 y;
    }

    /// @dev Ensures that `v` is approximately normed (i.e., lies on the unit circle).
    function validateNormed(Vector2 memory v, uint256 error_code) internal pure {
        int256 norm = v.x.mulDown(v.x);
        norm = norm.add(v.y.mulDown(v.y));
        _require(
            SignedFixedPoint.ONE - VALIDATION_PRECISION_NORMED_INPUT <= norm && norm <= SignedFixedPoint.ONE + VALIDATION_PRECISION_NORMED_INPUT,
            error_code
        );
    }

    /** @dev Ensures `derived ~ mkDerivedParams(params)`, without having to compute a square root.
     * This is useful mainly for numerical precision. */
    function validateDerivedParams(Params memory params, DerivedParams memory derived) internal pure {
        // tau vectors need to be normed b/c they're points on the unit circle.
        // This ensures that the tau value is = tau(px) for *some* px.
        validateNormed(derived.tauAlpha, GyroCEMMPoolErrors.DERIVED_TAU_NOT_NORMALIZED);
        validateNormed(derived.tauBeta, GyroCEMMPoolErrors.DERIVED_TAU_NOT_NORMALIZED);

        // It is easy to see that from the definition of eta that the underlying pxc value can be extracted as .x/.y.
        // This should be equal to the corresponding zeta value. We can compare for actual equality.
        int256 pxc = derived.tauAlpha.x.divUp(derived.tauAlpha.y);
        int256 pxc_computed = zeta(params, params.alpha);
        _require(
            pxc - VALIDATION_PRECISION_ZETA <= pxc_computed && pxc_computed <= pxc + VALIDATION_PRECISION_ZETA,
            GyroCEMMPoolErrors.DERIVED_ZETA_WRONG
        );

        pxc = derived.tauBeta.x.divUp(derived.tauBeta.y);
        pxc_computed = zeta(params, params.beta);
        _require(
            pxc - VALIDATION_PRECISION_ZETA <= pxc_computed && pxc_computed <= pxc + VALIDATION_PRECISION_ZETA,
            GyroCEMMPoolErrors.DERIVED_ZETA_WRONG
        );
    }

    // Scalar product of Vector2 objects
    function scalarProdUp(Vector2 memory t1, Vector2 memory t2) internal pure returns (int256 ret) {
        ret = t1.x.mulUp(t2.x).add(t1.y.mulUp(t2.y));
    }

    function scalarProdDown(Vector2 memory t1, Vector2 memory t2) internal pure returns (int256 ret) {
        ret = t1.x.mulDown(t2.x).add(t1.y.mulDown(t2.y));
    }

    // "Methods" for Params. We could put these into a separate library and import them via 'using' to get method call
    // syntax.

    /** @dev Calculate A^{-1}t where A^{-1} is given in Section 2.2
     *  This is rotating and scaling the circle into the ellipse */
    function mulAinv(Params memory params, Vector2 memory t) internal pure returns (Vector2 memory tp) {
        tp.x = t.x.mulDown(params.lambda).mulDown(params.c).add(params.s.mulDown(t.y));
        tp.y = (-t.x.mulDown(params.lambda).mulDown(params.s)).add(params.c.mulDown(t.y));
    }

    /** @dev Calculate A t where A is given in Section 2.2
     *  This is reversing rotation and scaling of the ellipse (mapping back to circle) */
    function mulA(Params memory params, Vector2 memory tp) internal pure returns (Vector2 memory t) {
        t.x = params.c.mulDown(tp.x).divDown(params.lambda);
        t.x = t.x.sub(params.s.mulDown(tp.y).divDown(params.lambda));
        t.y = params.s.mulDown(tp.x).add(params.c.mulDown(tp.y));
    }

    /** @dev Given price px on the transformed ellipse, get the untransformed price pxc on the circle
     *  px = price of asset x in terms of asset y.
     *  See Definition 1 in Section 2.1.1 */
    function zeta(Params memory params, int256 px) internal pure returns (int256 pxc) {
        Vector2 memory nd = mulA(params, Vector2(-SignedFixedPoint.ONE, px));
        return -nd.y.divDown(nd.x);
    }

    /** @dev Given price px on the transformed ellipse, maps to the corresponding point on the untransformed normalized circle
     *  px = price of asset x in terms of asset y.
     *  See Definition 3 in Section 2.1.1 */
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

    function mkDerivedParams(Params memory params) internal pure returns (DerivedParams memory derived) {
        derived.tauAlpha = tau(params, params.alpha);
        derived.tauBeta = tau(params, params.beta);
    }

    /** @dev Given price on a circle, gives the normalized corresponding point on the circle centered at the origin
     *  pxc = price of asset x in terms of asset y (measured on the circle)
     *  Notice that the eta function does not depend on Params.
     *  See Definition 2 in Section 2.1.1 */
    function eta(int256 pxc) internal pure returns (Vector2 memory tpp) {
        int256 z = FixedPoint.powDown(FixedPoint.ONE.add(uint256(pxc.mulDown(pxc))), ONEHALF).toInt256();
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
    function virtualOffsets(
        Params memory params,
        DerivedParams memory derived,
        int256 invariant
    ) internal pure returns (Vector2 memory ab) {
        ab.x = invariant.mulDown(mulAinv(params, derived.tauBeta).x); // virtual offset a
        ab.y = invariant.mulDown(mulAinv(params, derived.tauAlpha).y); // virtual offset b
    }

    /** @dev Calculates a = r*(A^{-1}tau(beta))_x with optimal precision and rounding up in signed direction
     *   TODO: correct for underestimate of r, in this case, mulUp/mulDown might not matter */
    function virtualOffset0(
        Params memory params,
        DerivedParams memory derived,
        int256 invariant
    ) internal pure returns (int256 a) {
        if (derived.tauBeta.x > 0) {
            a = invariant.mulUp(params.lambda).mulUp(derived.tauBeta.x).mulUp(params.c);
        } else {
            a = invariant.mulDown(params.lambda).mulDown(derived.tauBeta.x).mulDown(params.c);
        }
        if (derived.tauBeta.y > 0) {
            a = a.add(invariant.mulUp(params.s).mulUp(derived.tauBeta.y));
        } else {
            a = a.add(invariant.mulDown(params.s).mulDown(derived.tauBeta.y));
        }
    }

    /** @dev Calculates b = r*(A^{-1}tau(alpha))_y with optimal precision and rounding up in signed direction
        TODO: correct for underestimate of r, in this case, mulUp/mulDown might not matter */
    function virtualOffset1(
        Params memory params,
        DerivedParams memory derived,
        int256 invariant
    ) internal pure returns (int256 b) {
        if (derived.tauAlpha.x < 0) {
            b = invariant.mulUp(params.lambda).mulUp(-derived.tauAlpha.x).mulUp(params.s);
        } else {
            b = -invariant.mulDown(params.lambda).mulDown(derived.tauAlpha.x).mulDown(params.s);
        }
        if (derived.tauAlpha.y > 0) {
            b = b.add(invariant.mulUp(params.c).mulUp(derived.tauAlpha.y));
        } else {
            b = b.add(invariant.mulDown(params.c).mulDown(derived.tauAlpha.y));
        }
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

    struct QParams {
        int256 a;
        int256 b;
        int256 c;
    }

    /** @dev Compute the invariant 'r' corresponding to the given values. The invariant can't be negative, but
     *  we use a signed value to store it because all the other calculations are happening with signed ints, too.
     *  Computes r according to Prop 13 in 2.2.1 Initialization from Real Reserves
     *  orders operations to achieve best precision
     *  computes an underestimate */
    function calculateInvariant(
        uint256[] memory balances,
        Params memory params,
        DerivedParams memory derived
    ) internal pure returns (uint256 uinvariant) {
        Vector2 memory vbalances = Vector2(balances[0].toInt256(), balances[1].toInt256());
        int256 AChi_x = calcAChi_x(params, derived);
        int256 AChiDivLambda_y = calcAChiDivLambda_y(params, derived);
        int256 AtAChi = calcAtAChi(vbalances.x, vbalances.y, params, derived, AChi_x);
        int256 sqrt = calcInvariantSqrt(vbalances.x, vbalances.y, params, AChi_x, AChiDivLambda_y);
        // A chi \cdot A chi > 1, so round it up to round denominator up
        int256 denominator = calcAChiAChi(params, AChi_x, AChiDivLambda_y).sub(ONE);
        int256 invariant = AtAChi.add(sqrt).divDown(denominator);
        return invariant.toUint256();
    }

    /// @dev calculate (A chi)_x, ignores rounding direction
    function calcAChi_x(Params memory p, DerivedParams memory d) internal pure returns (int256 val) {
        // sc * (tau(beta)_y - tau(alpha)_y) / lambda + tau(beta)_x + tau(alpha)_x
        val = p.s.mulDown(p.c).mulDown(d.tauBeta.y.sub(d.tauAlpha.y)).divDown(p.lambda);
        val = val.add(d.tauBeta.x.mulDown(p.c).mulDown(p.c)).add(d.tauAlpha.x.mulDown(p.s).mulDown(p.s));
        // possible rounding error is 7 considering that each variable <= 1 individually, but don't know which way
    }

    /// @dev calculate (A chi / lambda)_y, ignores rounding direction
    function calcAChiDivLambda_y(Params memory p, DerivedParams memory d) internal pure returns (int256 val) {
        // sc * (tau(beta)_x - tau(alpha)_x) + (s^2 tau(beta)_y + c^2 tau(alpha)_y) / lambda
        val = (p.s.mulDown(p.s).mulDown(d.tauBeta.y).add(p.c.mulDown(p.c).mulDown(d.tauAlpha.y)).divDown(p.lambda));
        val = val.add(p.s.mulDown(p.c).mulDown(d.tauBeta.x.sub(d.tauAlpha.x)));
        // possible rounding error is 8 considering that each variable <= 1 individually and lambda > 1, but don't know which way
    }

    /// @dev calculate At \cdot A chi, ignores rounding direction
    function calcAtAChi(
        int256 x,
        int256 y,
        Params memory p,
        DerivedParams memory d,
        int256 AChi_x
    ) internal pure returns (int256 val) {
        // (cx / lambda - sy / lambda) * (A chi)_x
        val = x.mulDown(p.c).divDown(p.lambda).sub(y.mulUp(p.s).divUp(p.lambda));
        val = val.mulDown(AChi_x);

        // (x lambda s + y lambda c) * sc * (tau(beta)_x - tau(alpha)_x)
        int256 term = x.mulDown(p.lambda).mulDown(p.s).add(y.mulDown(p.lambda).mulDown(p.c));
        val = val.add(term.mulDown(p.s).mulDown(p.c).mulDown(d.tauBeta.x.sub(d.tauAlpha.x)));

        // (sx+cy) * (s^2 tau(beta)_y + c^2 tau(alpha)_y)
        term = p.s.mulDown(p.s).mulDown(d.tauBeta.y).add(p.c.mulDown(p.c).mulDown(d.tauAlpha.y));
        val = val.add((x.mulDown(p.s).add(y.mulDown(p.c))).mulDown(term));
    }

    /// @dev calculates A chi \cdot A chi, corrects for rounding direction error to overestimate in signed direction
    function calcAChiAChi(
        Params memory p,
        int256 AChi_x,
        int256 AChiDivLambda_y
    ) internal pure returns (int256 val) {
        // ( sc * (tau(beta)_y - tau(alpha)_y) / lambda + tau(beta)_x + tau(alpha)_x ) ^ 2
        // add 7 in magnitude within the square to correct for rounding error
        val = AChi_x.addMag(7);
        val = val.mulUp(val);

        // lambda^2 * (A chi / lambda)_y ^ 2
        // add 8 in magnitude within square to correct for rounding error
        int256 term = AChiDivLambda_y.addMag(8);
        val = val.add(p.lambda.mulUp(p.lambda).mulUp(term).mulUp(term));
    }

    /// @dev calculate -(At)_x ^2 (A chi)_y ^2 + (At)_x ^2, rounding down in signed direction
    function calcMinAtxAChiySqPlusAtxSq(
        int256 x,
        int256 y,
        Params memory p,
        int256 AChiDivLambda_y
    ) internal pure returns (int256 val) {
        // first calculate -(At)_x ^2 (A chi)_y ^2
        // (cx - sy)^2 > 0, calculate as x^2 c^2 + y^2 s^2 - xy2cs
        val = x.mulUp(x).mulUp(p.c).mulUp(p.c).add(y.mulUp(y).mulUp(p.s).mulUp(p.s));
        val = val.sub(x.mulDown(y).mulDown(p.c * 2).mulDown(p.s));

        // * (A chi / lambda)_y ^ 2
        // add 8 in magnitude within the square to correct for rounding error
        int256 term = AChiDivLambda_y.addMag(8);

        // subtract 10 to account for rounding error in lambda^2 * (At)_x ^2
        val = (-val.mulUp(term).mulUp(term)).add(val.sub(10).divDown(p.lambda).divDown(p.lambda));
    }

    /// @dev calculate 2(At)_x * (At)_y * (A chi)_x * (A chi)_y, ignores rounding direction
    function calc2AtxAtyAChixAChiy(
        int256 x,
        int256 y,
        Params memory p,
        int256 AChi_x,
        int256 AChiDivLambda_y
    ) internal pure returns (int256 val) {
        // (x^2 - y^2) sc * 2 + yx (c^2 - s^2) * 2
        val = (x.mulDown(x).sub(y.mulDown(y))).mulDown(p.c).mulDown(p.s * 2);
        val = val.add(y.mulDown(x).mulDown((p.c.mulDown(p.c).sub(p.s.mulDown(p.s))) * 2));
        // * (A chi)_x * (A chi / lambda)_y
        val = val.mulDown(AChi_x).mulDown(AChiDivLambda_y);
    }

    /// @dev calculate -(At)_y ^2 (A chi)_x ^2 + (At)_y ^2, rounding down in signed direction
    function calcMinAtyAChixSqPlusAtySq(
        int256 x,
        int256 y,
        Params memory p,
        int256 AChi_x
    ) internal pure returns (int256 val) {
        val = x.mulUp(x).mulUp(p.s).mulUp(p.s).add(y.mulUp(y).mulUp(p.c).mulUp(p.c));
        val = val.add(x.mulUp(y).mulUp(p.s * 2).mulUp(p.c));
        // add 7 in magnitude within the square to correct for rounding error
        int256 term = AChi_x.addMag(7);

        // subtract 10 to account for rounding error in (At)_y ^2
        val = (-val.mulUp(term).mulUp(term)).add(val.sub(10));
    }

    function calcInvariantSqrt(
        int256 x,
        int256 y,
        Params memory p,
        int256 AChi_x,
        int256 AChiDivLambda_y
    ) internal pure returns (int256 val) {
        val = calcMinAtxAChiySqPlusAtxSq(x, y, p, AChiDivLambda_y).add(calc2AtxAtyAChixAChiy(x, y, p, AChi_x, AChiDivLambda_y));
        val = val.add(calcMinAtyAChixSqPlusAtySq(x, y, p, AChi_x));
        val = val.sub(100); // correct to downside for rounding error, given everything is O(eps) error propagation
        // mathematically, terms in square root > 0, so treat as 0 if it is < 0 b/c of rounding error
        val = val > 0 ? FixedPoint.powDown(val.toUint256(), ONEHALF).toInt256() : 0;
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
        int256 newBal,
        uint8 assetIndex
    ) internal pure {
        Vector2 memory xyPlus = maxBalances(params, derived, invariant);
        int256 factor = SignedFixedPoint.ONE.sub(_MIN_BAL_RATIO.toInt256());
        if (assetIndex == 0) {
            _require(newBal < xyPlus.x.mulDown(factor), GyroCEMMPoolErrors.ASSET_BOUNDS_EXCEEDED);
        } else {
            _require(newBal < xyPlus.y.mulDown(factor), GyroCEMMPoolErrors.ASSET_BOUNDS_EXCEEDED);
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
        function(int256, Params memory, DerivedParams memory, int256) pure returns (int256) calcGiven;
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
        int256 balInNew = balances[ixIn].add(amountIn).toInt256();
        checkAssetBounds(params, derived, uinvariant.toInt256(), balInNew, ixIn);
        int256 balOutNew = calcGiven(balInNew, params, derived, uinvariant.toInt256());
        uint256 assetBoundError = GyroCEMMPoolErrors.ASSET_BOUNDS_EXCEEDED;
        _require(balOutNew.toUint256() < balances[ixOut], assetBoundError);
        if (balOutNew >= balInNew) {
            _require(balInNew.divUp(balOutNew) > _MIN_BAL_RATIO.toInt256(), assetBoundError);
        } else {
            _require(balOutNew.divUp(balInNew) > _MIN_BAL_RATIO.toInt256(), assetBoundError);
        }
        amountOut = balances[ixOut].sub(balOutNew.toUint256());
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
        function(int256, Params memory, DerivedParams memory, int256) pure returns (int256) calcGiven;
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
        int256 balOutNew = balances[ixOut].sub(amountOut).toInt256();
        int256 balInNew = calcGiven(balOutNew, params, derived, uinvariant.toInt256());
        uint256 assetBoundError = GyroCEMMPoolErrors.ASSET_BOUNDS_EXCEEDED;
        _require(balInNew.toUint256() > balances[ixIn], assetBoundError);
        checkAssetBounds(params, derived, uinvariant.toInt256(), balInNew, ixIn);
        if (balOutNew >= balInNew) {
            _require(balInNew.divUp(balOutNew) > _MIN_BAL_RATIO.toInt256(), assetBoundError);
        } else {
            _require(balOutNew.divUp(balInNew) > _MIN_BAL_RATIO.toInt256(), assetBoundError);
        }
        amountIn = balInNew.toUint256().sub(balances[ixIn]);
        _require(amountIn <= balances[ixIn].mulDown(_MAX_IN_RATIO), Errors.MAX_IN_RATIO);
    }

    /** @dev Variables are named for calculating y given x
     *  to calculate x given y, change x->y, s->c, c->s, a_>b, b->a, tauBeta.x -> -tauAlpha.x, tauBeta.y -> tauAlpha.y
     *  TODO: account for error in b (from r) and thus also x-b */
    function solveQuadraticSwap(
        int256 lambda,
        int256 x,
        int256 s,
        int256 c,
        int256 r,
        Vector2 memory ab,
        Vector2 memory tauBeta
    ) internal pure returns (int256) {
        Vector2 memory lamBar; // x component will round up, y will round down
        lamBar.x = ONE.sub(ONE.divDown(lambda).divDown(lambda));
        lamBar.y = ONE.sub(ONE.divUp(lambda).divUp(lambda));
        QParams memory qparams;

        // shift by the virtual offsets
        // note that we want an overestimate of offset here so that -x'*lambar*s*c is overestimated in signed direction
        int256 xp = x.sub(ab.x);
        qparams.b = xp > 0 ? -xp.mulDown(lamBar.y).mulDown(s).mulDown(c) : (-xp).mulUp(lamBar.x).mulUp(s).mulUp(c);

        // x component will round up, y will round down
        Vector2 memory sTerm = Vector2(ONE.sub(lamBar.y.mulDown(s).mulDown(s)), ONE.sub(lamBar.x.mulUp(s).mulUp(s)));

        // now compute the argument of the square root
        qparams.c = -calcXpXpDivLambdaLambda(x, r, lambda, s, c, ab.x, tauBeta);
        qparams.c = qparams.c.add(r.mulDown(r).mulDown(sTerm.y));

        // mathematically, terms in square root > 0, so treat as 0 if it is < 0 b/c of rounding error
        qparams.c = qparams.c > 0 ? FixedPoint.powDown(qparams.c.toUint256(), ONEHALF).toInt256() : 0;
        // calculate the result in qparams.a
        qparams.a = qparams.b - qparams.c > 0 ? (qparams.b.sub(qparams.c)).divUp(sTerm.y) : (qparams.b.sub(qparams.c)).divDown(sTerm.x);
        // note that we want an overestimate of offset here
        return qparams.a.add(ab.y);
    }

    /** @dev Calculates x'x' where x' = x - b = x - r (A^{-1}tau(beta))_x
     *  calculates an overestimate
     *  to calculate y'y', change x->y, s->c, c->s, tauBeta.x -> -tauAlpha.x, tauBeta.y -> tauAlpha.y  */
    function calcXpXpDivLambdaLambda(
        int256 x,
        int256 r,
        int256 lambda,
        int256 s,
        int256 c,
        int256 a,
        Vector2 memory tauBeta
    ) internal pure returns (int256 val) {
        // We want to overestimate x' in magnitude b/c it will be squared
        // if x' > 0 then we want an underestimate of offsets (and so an underestimate of r), so we reverse the earlier correction
        // if x' < 0 then we are good with the overestimate
        r = x - a > 0 ? r.add(r.mulUp(1e6)) : r;

        // r^2 tau(beta)_x^2 c^2
        val = r.mulUp(r).mulUp(tauBeta.x).mulUp(tauBeta.x);
        val = val.mulUp(c).mulUp(c);

        // (r^2 s tau(beta)_y - rx)2c tau(beta)_x / lambda
        // add 8 to accout for rounding error in numerator, considering magnitude of terms
        int256 term = r.mulDown(r).mulDown(s).mulDown(tauBeta.y).sub(r.mulDown(x));
        term = term.mulDown(2 * c).mulDown(tauBeta.x) + 8;
        val = term > 0 ? val.add(term.divUp(lambda)) : val.add(term.divDown(lambda));

        // ((r^2 s tau(beta)_y - rx 2) s tau(beta)_y + x^2) / lambda^2
        // add 9 to account for rounding error in numerator, considering magnitude of terms
        term = r.mulDown(r).mulDown(s).mulDown(tauBeta.y);
        term = term.sub(r.mulDown(x).mulDown(2 * ONE));
        term = term.mulDown(s).mulDown(tauBeta.y).add(x.mulUp(x)) + 9;
        val = term > 0 ? val.add(term.divUp(lambda).divUp(lambda)) : val.add(term.divDown(lambda).divDown(lambda));
    }

    /** @dev compute y such that (x, y) satisfy the invariant at the given parameters.
     *   See Prop 14 in section 2.2.2 Trade Execution */
    function calcYGivenX(
        int256 x,
        Params memory params,
        DerivedParams memory derived,
        int256 invariant
    ) internal pure returns (int256 y) {
        // calculate an overestimate of invariant, which has relative error 1e-14, take two extra decimal places to be safe
        // note that the error correction here should more than make up for rounding directions in virtual offset functions
        int256 invariantUp = invariant.add(invariant.mulUp(1e6));
        // want to overestimate the virtual offsets except in a particular setting that will be corrected for later
        Vector2 memory ab = Vector2(virtualOffset0(params, derived, invariantUp), virtualOffset1(params, derived, invariantUp));
        y = solveQuadraticSwap(params.lambda, x, params.s, params.c, invariant, ab, derived.tauBeta);
    }

    function calcXGivenY(
        int256 y,
        Params memory params,
        DerivedParams memory derived,
        int256 invariant
    ) internal pure returns (int256 x) {
        // calculate an overestimate of invariant, which has relative error 1e-14, take two extra decimal places to be safe
        // note that the error correction here should more than make up for rounding directions in virtual offset functions
        int256 invariantUp = invariant.add(invariant.mulUp(1e6));
        // want to overestimate the virtual offsets except in a particular setting that will be corrected for later
        Vector2 memory ba = Vector2(virtualOffset1(params, derived, invariantUp), virtualOffset0(params, derived, invariantUp));
        // change x->y, s->c, c->s, b->a, a->b, tauBeta.x -> -tauAlpha.x, tauBeta.y -> tauAlpha.y vs calcYGivenX
        x = solveQuadraticSwap(params.lambda, y, params.c, params.s, invariant, ba, Vector2(-derived.tauAlpha.x, derived.tauAlpha.y));
    }

    /** @dev calculates x*y*lambda with extra precision
     *  assumes x,y, lambda > 0 and that lambda only has 3 significant decimal digits (0s after)
     *  guaranteed not to overflow for x,y < 1e12 and lambda < 1e8 with some digits of wiggle room above that
     *  Rounds in magnitude in direction given by roundUp */
    function mulXpInXYLambda(
        int256 x,
        int256 y,
        int256 lambda,
        bool roundUp
    ) internal pure returns (int256) {
        int256 prod = x * y;
        _require(x == 0 || prod / x == y, Errors.MUL_OVERFLOW);
        int256 nextProd = prod * (lambda / 1e15);
        _require(prod == 0 || nextProd / prod == lambda / 1e15, Errors.MUL_OVERFLOW);
        return roundUp ? (nextProd - 1) / 1e21 + 1 : nextProd / 1e21;
    }

    /** @dev calculates x*y*lambda*lambda with extra precision
     *  assumes x,y, lambda > 0 and that lambda only has 3 significant decimal digits (0s after)
     *  guaranteed not to overflow for x,y < 1e12 and lambda < 1e8 with some digits of wiggle room above that
     *  Rounds in magnitude in direction given by roundUp */
    function mulXpInXYLambdaLambda(
        int256 x,
        int256 y,
        int256 lambda,
        bool roundUp
    ) internal pure returns (int256) {
        int256 prod = x * y;
        _require(x == 0 || prod / x == y, Errors.MUL_OVERFLOW);
        int256 nextProd = prod * (lambda / 1e15);
        _require(prod == 0 || nextProd / prod == lambda / 1e15, Errors.MUL_OVERFLOW);
        prod = roundUp ? (nextProd - 1) / 1e13 + 1 : nextProd / 1e13;

        nextProd = prod * (lambda / 1e15);
        _require(prod == 0 || nextProd / prod == lambda / 1e15, Errors.MUL_OVERFLOW);
        return roundUp ? (nextProd - 1) / 1e11 + 1 : nextProd / 1e11;
    }
}
