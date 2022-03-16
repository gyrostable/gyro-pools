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
        int256 d;
        int256 dAlpha;
        int256 dBeta;
    }

    function validateParams(Params memory params) internal pure {
        _require(params.alpha > 0, GyroCEMMPoolErrors.PRICE_BOUNDS_WRONG);
        _require(params.beta > params.alpha, GyroCEMMPoolErrors.PRICE_BOUNDS_WRONG);
        _require(params.c >= 0, GyroCEMMPoolErrors.ROTATION_VECTOR_WRONG);
        _require(params.s >= 0, GyroCEMMPoolErrors.ROTATION_VECTOR_WRONG);
        _require(params.lambda >= 1, GyroCEMMPoolErrors.STRETCHING_FACTOR_WRONG);
        validateNormed(Vector2(params.c, params.s), GyroCEMMPoolErrors.ROTATION_VECTOR_NOT_NORMALIZED);
    }

    struct DerivedParams {
        Vector2 tauAlpha;
        Vector2 tauBeta;
        int256 u;
        int256 v;
        int256 w;
        int256 z;
    }

    struct Vector2 {
        int256 x;
        int256 y;
    }

    struct QParams {
        int256 a;
        int256 b;
        int256 c;
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

    function scalarProd(Vector2 memory t1, Vector2 memory t2) internal pure returns (int256 ret) {
        ret = t1.x.mulDown(t2.x).add(t1.y.mulDown(t2.y));
    }

    // "Methods" for Params. We could put these into a separate library and import them via 'using' to get method call
    // syntax.

    /** @dev Calculate A t where A is given in Section 2.2
     *  This is reversing rotation and scaling of the ellipse (mapping back to circle) */
    function mulA(Params memory params, Vector2 memory tp) internal pure returns (Vector2 memory t) {
        t.x = params.c.mulDown(tp.x).divDown(params.lambda).sub(params.s.mulDown(tp.y).divDown(params.lambda));
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

    function tauXp(
        Params memory p,
        int256 px,
        int256 dPx
    ) internal pure returns (Vector2 memory tauPx) {
        tauPx.x = (p.c * 1e20 - (p.s * 1e20).divXp(px * 1e20)).mulXp(dPx);
        tauPx.y = (p.s * 1e20 + (p.c * 1e20).divXp(px * 1e20)).divXp(p.lambda * 1e20).mulXp(dPx);
    }

    /// make derived params in extra precision, intentionally missing a factor of 1/d where s^2 + c^2 = d^2
    function mkDerivedParamsXp(Params memory p) internal pure returns (DerivedParams memory d) {
        d.tauAlpha = tauXp(p, p.alpha, p.dAlpha);
        d.tauBeta = tauXp(p, p.beta, p.dBeta);
        // w = sc (tau(beta)_y - tau(alpha)_y
        d.w = (p.s * 1e20).mulXp(p.c * 1e20).mulXp(d.tauBeta.y.sub(d.tauAlpha.y));
        // z = c^2 tau(beta)_x + s^2 tau(alpha)_x
        d.z = (p.c * 1e20).mulXp(p.c * 1e20).mulXp(d.tauBeta.x);
        d.z = d.z.add((p.s * 1e20)).mulXp(p.s * 1e20).mulXp(d.tauAlpha.x);
        // u = sc (tau(beta)_x - tau(alpha)_x)
        d.u = (p.s * 1e20).mulXp(p.c * 1e20).mulXp(d.tauBeta.x.sub(d.tauAlpha.x));
        // v = s^2 tau(beta)_y + c^2 tau(alpha)_y
        d.v = (p.s * 1e20).mulXp(p.s * 1e20).mulXp(d.tauBeta.y);
        d.v = d.v.add((p.c * 1e20).mulXp(p.c * 1e20).mulXp(d.tauAlpha.y));
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

    /** @dev Calculate virtual offset a given invariant r.
     *  See calculation in Section 2.1.2 Computing reserve offsets
     *  Note that, in contrast to virtual reserve offsets in CPMM, these are *subtracted* from the real
     *  reserves, moving the curve to the upper-right. They can be positive or negative, but not both can be negative.
     *  Calculates a = r*(A^{-1}tau(beta))_x with optimal precision and rounding up in signed direction */
    function virtualOffset0(
        Params memory p,
        DerivedParams memory d,
        Vector2 memory r // overestimate in x component, underestimate in y
    ) internal pure returns (int256 a) {
        a = (d.tauBeta.x > 0) ? r.x.mulUp(p.lambda).mulUp(d.tauBeta.x).mulUp(p.c) : r.y.mulDown(p.lambda).mulDown(d.tauBeta.x).mulDown(p.c);
        a = (d.tauBeta.y > 0) ? a.add(r.x.mulUp(p.s).mulUp(d.tauBeta.y)) : a.add(r.y.mulDown(p.s).mulDown(d.tauBeta.y));
    }

    /** @dev calculate virtual offset b given invariant r.
     *  Calculates b = r*(A^{-1}tau(alpha))_y with optimal precision and rounding up in signed direction */
    function virtualOffset1(
        Params memory p,
        DerivedParams memory d,
        Vector2 memory r // overestimate in x component, underestimate in y
    ) internal pure returns (int256 b) {
        b = (d.tauAlpha.x < 0) ? r.x.mulUp(p.lambda).mulUp(-d.tauAlpha.x).mulUp(p.s) : -r.y.mulDown(p.lambda).mulDown(d.tauAlpha.x).mulDown(p.s);
        b = (d.tauAlpha.y > 0) ? b.add(r.x.mulUp(p.c).mulUp(d.tauAlpha.y)) : b.add(r.y.mulDown(p.c).mulDown(d.tauAlpha.y));
    }

    /** Maximal value for the real reserves x when the respective other balance is 0 for given invariant
     *  See calculation in Section 2.1.2. Calculation is ordered here for optimal precision
     *  Rounding direction is ignored but is small considering precision, and is corrected for later */
    function maxBalances0(
        Params memory p,
        DerivedParams memory d,
        int256 invariant
    ) internal pure returns (int256 xp) {
        // r lambda c (tau(beta)_x - tau(alpha)_x) + rs (tau(beta)_y - tau(alpha)_y)
        xp = invariant.mulDown(p.lambda).mulDown(p.c).mulDown(d.tauBeta.x.sub(d.tauAlpha.x));
        xp = xp.add(invariant.mulDown(p.s).mulDown(d.tauBeta.y.sub(d.tauAlpha.y)));
    }

    /** Maximal value for the real reserves y when the respective other balance is 0 for given invariant
     *  See calculation in Section 2.1.2. Calculation is ordered here for optimal precision
     *  Rounding direction is ignored but is small considering precision, and is corrected for later */
    function maxBalances1(
        Params memory p,
        DerivedParams memory d,
        int256 invariant
    ) internal pure returns (int256 yp) {
        // r lambda s (tau(beta)_x - tau(alpha)_x) + rc (tau(alpha)_y - tau(beta)_y)
        yp = invariant.mulDown(p.lambda).mulDown(p.s).mulDown(d.tauBeta.x.sub(d.tauAlpha.x));
        yp = yp.add(invariant.mulDown(p.c).mulDown(d.tauAlpha.y.sub(d.tauBeta.y)));
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
        Vector2 memory AChi_y = calcAChiDivLambda_y(params, derived);
        int256 AtAChi = calcAtAChi(vbalances.x, vbalances.y, params, derived, AChi_x);
        int256 sqrt = calcInvariantSqrt(vbalances.x, vbalances.y, params, AChi_x, AChi_y);
        // A chi \cdot A chi > 1, so round it up to round denominator up
        int256 denominator = calcAChiAChi(params, AChi_x, AChi_y).sub(ONE);
        int256 invariant = AtAChi.add(sqrt).divDown(denominator);
        return invariant.toUint256();
    }

    /// @dev calculate (A chi)_x, rounds up in signed direction
    function calcAChi_x(Params memory p, DerivedParams memory d) internal pure returns (int256 val) {
        // sc * (tau(beta)_y - tau(alpha)_y) / lambda + tau(beta)_x + tau(alpha)_x
        val = d.tauBeta.y.sub(d.tauAlpha.y);
        val = val > 0 ? p.s.mulUp(p.c).mulUp(val).divUp(p.lambda) : p.s.mulDown(p.c).mulDown(val).divDown(p.lambda);
        val = val.add(d.tauBeta.x > 0 ? d.tauBeta.x.mulUp(p.c).mulUp(p.c) : d.tauBeta.x.mulDown(p.c).mulDown(p.c));
        val = val.add(d.tauAlpha.x > 0 ? d.tauAlpha.x.mulUp(p.s).mulUp(p.s) : d.tauAlpha.x.mulDown(p.s).mulDown(p.s));
        // possible rounding error is 7 considering that each variable <= 1 individually, but don't know which way
    }

    /// @dev calculate terms of (A chi)_y excluding terms with lambda (these will later be accounted for in the best order)
    /// returns Vector2: x contains terms that should contain lambda factor, y contains other terms
    /// rounds x,y components up in signed direction
    function calcAChiDivLambda_y(Params memory p, DerivedParams memory d) internal pure returns (Vector2 memory val) {
        // (A chi)_y = sc * (tau(beta)_x - tau(alpha)_x) * lambda + (s^2 tau(beta)_y + c^2 tau(alpha)_y)
        val.x = d.tauBeta.x.sub(d.tauAlpha.x);
        val.x = val.x > 0 ? p.s.mulUp(p.c).mulUp(val.x) : p.s.mulDown(p.c).mulDown(val.x);
        val.y = d.tauBeta.y > 0 ? p.s.mulUp(p.s).mulUp(d.tauBeta.y) : p.s.mulDown(p.s).mulDown(d.tauBeta.y);
        val.y = val.y.add(d.tauAlpha.y > 0 ? p.c.mulUp(p.c).mulUp(d.tauAlpha.y) : p.c.mulDown(p.c).mulDown(d.tauAlpha.y));
        // possible rounding error in val.x is 3
        // possible rounding error in val.y is 5
        // this considers that each variable <= 1 individually
    }

    /// @dev calculates termToMul * (zu + (wu+zv)/lambda + wv/lambda^2)
    /// to calculate (A chi)_x^2, use z,w from ( A chi)_x = z + w/lambda, and set u=z, v=w
    /// to calculate (A chi/lambda)_y^2, use u,v fromt (A chi)_y = lambda u + v, and set z=u, w=v
    /// to calculate (A chi)_x (A chi/lambda)_y, use u,v,z,w as given
    function mulAChiFactors(
        int256 termToMul,
        int256 w,
        int256 z,
        int256 u,
        int256 v,
        int256 lambda
    ) internal pure returns (int256 val) {
        val = termToMul.mulDown(z).mulDown(u);
        val = val.add(termToMul.mulDown(w.mulDown(u).add(z.mulDown(v))).divDown(lambda));
        val = val.add(termToMul.mulDown(w).mulDown(v).divDown(lambda).divDown(lambda));
    }

    /// @dev calculate At \cdot A chi, ignores rounding direction
    // TODO: make this round down
    function calcAtAChi(
        int256 x,
        int256 y,
        Params memory p,
        DerivedParams memory d,
        int256 AChi_x
    ) internal pure returns (int256 val) {
        // (cx - sy) * (A chi)_x / lambda
        val = (x.mulDown(p.c).sub(y.mulDown(p.s))).mulDown(AChi_x).divDown(p.lambda);

        // (x lambda s + y lambda c) * sc * (tau(beta)_x - tau(alpha)_x)
        int256 term = x.mulDown(p.lambda).mulDown(p.s).add(y.mulDown(p.lambda).mulDown(p.c));
        val = val.add(term.mulDown(p.s).mulDown(p.c).mulDown(d.tauBeta.x.sub(d.tauAlpha.x)));

        // (sx+cy) * (s^2 tau(beta)_y + c^2 tau(alpha)_y)
        term = p.s.mulDown(p.s).mulDown(d.tauBeta.y).add(p.c.mulDown(p.c).mulDown(d.tauAlpha.y));
        val = val.add((x.mulDown(p.s).add(y.mulDown(p.c))).mulDown(term));
    }

    /// @dev calculates A chi \cdot A chi, overestimates in signed direction
    function calcAChiAChi(
        Params memory p,
        int256 AChi_x,
        Vector2 memory AChi_y // x contains terms *lambda, y contains other terms
    ) internal pure returns (int256 val) {
        // (A chi)_y^2 = lambda^2 v^2 + lambda 2 v w + w^2, where (v,w) = AChi_y
        // - 3 and 5 to account for rounding error in v, w
        val = AChi_y.x * AChi_y.y > 0
            ? p.lambda.mulUp(2 * AChi_y.x).mulUp(AChi_y.y)
            : p.lambda.mulDown(2 * AChi_y.x.addMag(-3)).mulDown(AChi_y.y.addMag(-5));
        val = val.add(p.lambda.mulUp(p.lambda).mulUp(AChi_y.x).mulUp(AChi_y.x)).add(AChi_y.y.mulUp(AChi_y.y));

        // (A chi)_x^2 = ( sc * (tau(beta)_y - tau(alpha)_y) / lambda + tau(beta)_x + tau(alpha)_x ) ^ 2
        val = val.add(AChi_x.mulUp(AChi_x));
    }

    /// @dev calculate -(At)_x ^2 (A chi)_y ^2 + (At)_x ^2, rounding down in signed direction
    function calcMinAtxAChiySqPlusAtxSq(
        int256 x,
        int256 y,
        Params memory p,
        Vector2 memory AChi_y // x contains terms *lambda, y contains other terms
    ) internal pure returns (int256 val) {
        // first calculate -(At)_x ^2 (A chi)_y ^2

        // (cx - sy)^2 > 0, calculate as x^2 c^2 + y^2 s^2 - xy2cs
        val = x.mulUp(x).mulUp(p.c).mulUp(p.c).add(y.mulUp(y).mulUp(p.s).mulUp(p.s));
        val = val.sub(x.mulDown(y).mulDown(p.c * 2).mulDown(p.s));
        // * (A chi / lambda)_y ^ 2, by strategically ordering the /lambda
        // considering (A chi)_y^2 = lambda^2 v^2 + lambda 2 v w + w^2, where (v,w) = AChi_y
        // - 3 and 5 to account for rounding error in v, w
        int256 term = val.mulUp(AChi_y.x).mulUp(AChi_y.x);
        if (AChi_y.x & AChi_y.y > 0) {
            term = term.add(val.mulUp(2 * AChi_y.x).mulUp(AChi_y.y).divUp(p.lambda));
        } else {
            term = term.add(val.mulDown(2 * AChi_y.x.addMag(-3)).mulDown(AChi_y.y.addMag(-5)));
        }
        term = term.add(val.mulUp(AChi_y.y).mulUp(AChi_y.y).divUp(p.lambda).divUp(p.lambda));

        // account for rounding error in x^2 c^2 + y^2 s^2 - xy2cs
        // error is ~ 2*(x^2 + y^2) * 1e-18
        int256 err = (x.mulUp(x).add(y.mulUp(y)) / ONE) * 3;
        val = (-term).add(val.sub(err).divDown(p.lambda).divDown(p.lambda));
    }

    /// @dev calculate 2(At)_x * (At)_y * (A chi)_x * (A chi)_y, accounts for error to round down
    // TODO: confirm this round down
    function calc2AtxAtyAChixAChiy(
        int256 x,
        int256 y,
        Params memory p,
        int256 AChi_x,
        Vector2 memory AChi_y // x contains terms *lambda, y contains other terms
    ) internal pure returns (int256 val) {
        // (x^2 - y^2) sc * 2 + yx (c^2 - s^2) * 2
        val = x.mulDown(x).sub(y.mulUp(y)).mulDown(p.c * 2).mulDown(p.s);
        val = val.add(y.mulDown(x).mulDown((p.c.mulDown(p.c).sub(p.s.mulDown(p.s))) * 2));
        // * (A chi)_x
        val = val.mulDown(AChi_x);
        // * (A chi / lambda)_y, by strategically ordering the /lambda
        // considering (A chi)_y = lambda v + w, where (v,w) = AChi_y
        // first account for possible rounding error: ~ O((x^2 + y^2)*1e-18)
        int256 err = ((x.mulUp(x).sub(y.mulUp(y)).add(y.mulUp(x))) / ONE) * 17;
        err = err > 0 ? err : -err;
        val = val.mulDown(AChi_y.x).sub(err);
        val = val.add(val.mulDown(AChi_y.y).sub(err).divDown(p.lambda));
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
        int256 term = AChi_x;

        // account for rounding error in (At)_y ^2
        int256 err = (x.mulUp(x).add(y.mulUp(y)) / ONE) * 3;
        val = (-val.mulUp(term).mulUp(term)).add(val.sub(err));
    }

    // TODO: properly account for any residual rounding error
    function calcInvariantSqrt(
        int256 x,
        int256 y,
        Params memory p,
        int256 AChi_x,
        Vector2 memory AChi_y
    ) internal pure returns (int256 val) {
        val = calcMinAtxAChiySqPlusAtxSq(x, y, p, AChi_y).add(calc2AtxAtyAChixAChiy(x, y, p, AChi_x, AChi_y));
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
        Vector2 memory r = Vector2(invariantOverestimate(invariant), invariant);
        Vector2 memory ab = Vector2(virtualOffset0(params, derived, r), virtualOffset1(params, derived, r));
        Vector2 memory vec = Vector2(balances[0].toInt256().sub(ab.x), balances[1].toInt256().sub(ab.y));

        // transform to circle to get Av(t)
        vec = mulA(params, vec);
        // compute prices on circle
        Vector2 memory pc = Vector2(vec.x.divDown(vec.y), ONE);

        // Convert prices back to ellipse
        int256 pgx = scalarProd(pc, mulA(params, Vector2(ONE, 0)));
        px = pgx.divDown(scalarProd(pc, mulA(params, Vector2(0, ONE)))).toUint256();
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
        int256 factor = ONE.sub(_MIN_BAL_RATIO.toInt256());
        if (assetIndex == 0) {
            int256 xPlus = maxBalances0(params, derived, invariant);
            _require(newBal < xPlus.mulDown(factor), GyroCEMMPoolErrors.ASSET_BOUNDS_EXCEEDED);
        } else {
            int256 yPlus = maxBalances1(params, derived, invariant);
            _require(newBal < yPlus.mulDown(factor), GyroCEMMPoolErrors.ASSET_BOUNDS_EXCEEDED);
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
     *  to calculate x given y, change x->y, s->c, c->s, a_>b, b->a, tauBeta.x -> -tauAlpha.x, tauBeta.y -> tauAlpha.y */
    function solveQuadraticSwap(
        int256 lambda,
        int256 x,
        int256 s,
        int256 c,
        Vector2 memory r, // overestimate in x component, underestimate in y
        Vector2 memory ab,
        Vector2 memory tauBeta
    ) internal pure returns (int256) {
        // x component will round up, y will round down
        Vector2 memory lamBar = Vector2(ONE.sub(ONE.divDown(lambda).divDown(lambda)), ONE.sub(ONE.divUp(lambda).divUp(lambda)));
        QParams memory qparams;

        // shift by the virtual offsets
        // note that we want an overestimate of offset here so that -x'*lambar*s*c is overestimated in signed direction
        int256 xp = x.sub(ab.x);
        qparams.b = xp > 0 ? -xp.mulDown(lamBar.y).mulDown(s).mulDown(c) : (-xp).mulUp(lamBar.x).mulUp(s).mulUp(c);

        // x component will round up, y will round down
        Vector2 memory sTerm = Vector2(ONE.sub(lamBar.y.mulDown(s).mulDown(s)), ONE.sub(lamBar.x.mulUp(s).mulUp(s)));

        // now compute the argument of the square root, subtract 100 to account for rounding errors
        qparams.c = -calcXpXpDivLambdaLambda(x, r, lambda, s, c, tauBeta);
        qparams.c = qparams.c.add(r.y.mulDown(r.y).mulDown(sTerm.y)).sub(100);

        // the square root is always being subtracted, so round it down to overestimate the end balance
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
        Vector2 memory r, // overestimate in x component, underestimate in y
        int256 lambda,
        int256 s,
        int256 c,
        Vector2 memory tauBeta
    ) internal pure returns (int256) {
        //////////////////////////////////////////////////////////////////////////////////
        // x'x'/lambda^2 = r^2 tau(beta)_x^2 c^2
        //      + ( r^2 2 cs tau(beta)_x tau(beta)_y - rx 2c tau(beta)_x ) / lambda
        //      + ( r^2 s^2 tau(beta)_y^2 - rx 2s tau(beta)_y + x^2 ) / lambda^2
        //////////////////////////////////////////////////////////////////////////////////

        QParams memory q; // for working terms
        // q.a = r^2 s tau(beta)_y 2c tau(beta)_x
        if (tauBeta.y * tauBeta.x > 0) {
            q.a = r.x.mulUp(r.x).mulUp(2 * s).mulUp(tauBeta.y);
            q.a = q.a.mulUp(c).mulUp(tauBeta.x);
        } else {
            q.a = r.y.mulDown(r.y).mulDown(2 * s).mulDown(tauBeta.y);
            q.a = q.a.mulDown(c).mulDown(tauBeta.x);
        }
        // -rx 2c tau(beta)_x
        q.b = tauBeta.x < 0 ? r.x.mulUp(x).mulUp(2 * c).mulUp(-tauBeta.x) : -r.y.mulDown(x).mulDown(2 * c).mulDown(tauBeta.x);
        // q.a later needs to be divided by lambda
        q.a = q.a.add(q.b);

        // q.b = r^2 s^2 tau(beta)_y^2
        q.b = r.x.mulUp(r.x).mulUp(s).mulUp(s);
        q.b = q.b.mulUp(tauBeta.y).mulUp(tauBeta.y);
        // q.c = -rx 2s tau(beta)_y
        q.c = tauBeta.y < 0 ? r.x.mulUp(x).mulUp(2 * s).mulUp(-tauBeta.y) : -r.y.mulDown(x).mulDown(2 * s).mulDown(tauBeta.y);
        // (q.b + q.c + x^2) / lambda
        q.b = (q.b.add(q.c).add(x.mulUp(x)));
        q.b = q.b > 0 ? q.b.divUp(lambda) : q.b.divDown(lambda);

        // remaining calculation is (q.a + q.b) / lambda
        q.a = q.a.add(q.b);
        q.a = q.a > 0 ? q.a.divUp(lambda) : q.a.divDown(lambda);

        // + r^2 tau(beta)_x^2 c^2
        int256 val = r.x.mulUp(r.x).mulUp(tauBeta.x).mulUp(tauBeta.x);
        return val.mulUp(c).mulUp(c).add(q.a);
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
        // overestimate in x component, underestimate in y
        Vector2 memory r = Vector2(invariantOverestimate(invariant), invariant);
        // want to overestimate the virtual offsets except in a particular setting that will be corrected for later
        Vector2 memory ab = Vector2(virtualOffset0(params, derived, r), virtualOffset1(params, derived, r));
        y = solveQuadraticSwap(params.lambda, x, params.s, params.c, r, ab, derived.tauBeta);
    }

    function calcXGivenY(
        int256 y,
        Params memory params,
        DerivedParams memory derived,
        int256 invariant
    ) internal pure returns (int256 x) {
        // calculate an overestimate of invariant, which has relative error 1e-14, take two extra decimal places to be safe
        // note that the error correction here should more than make up for rounding directions in virtual offset functions
        // overestimate in x component, underestimate in y
        Vector2 memory r = Vector2(invariantOverestimate(invariant), invariant);
        // want to overestimate the virtual offsets except in a particular setting that will be corrected for later
        Vector2 memory ba = Vector2(virtualOffset1(params, derived, r), virtualOffset0(params, derived, r));
        // change x->y, s->c, c->s, b->a, a->b, tauBeta.x -> -tauAlpha.x, tauBeta.y -> tauAlpha.y vs calcYGivenX
        x = solveQuadraticSwap(params.lambda, y, params.c, params.s, r, ba, Vector2(-derived.tauAlpha.x, derived.tauAlpha.y));
    }

    /// @dev Given an underestimate of invariant, calculate an overestimate by accounting for error
    function invariantOverestimate(int256 rDown) internal pure returns (int256 rUp) {
        rUp = rDown.add(rDown.mulUp(1e6));
    }
}
