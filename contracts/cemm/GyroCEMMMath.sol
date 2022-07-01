pragma solidity ^0.7.0;

import "@balancer-labs/v2-solidity-utils/contracts/math/FixedPoint.sol";
import "../../libraries/SignedFixedPoint.sol";
import "../../libraries/GyroPoolMath.sol";
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
    int256 internal constant ONE_XP = 1e38; // 38 decimal places

    using SignedFixedPoint for int256;
    using FixedPoint for uint256;
    using SafeCast for uint256;
    using SafeCast for int256;

    // Swap limits: amounts swapped may not be larger than this percentage of total balance.
    uint256 internal constant _MAX_IN_RATIO = 0.3e18;
    uint256 internal constant _MAX_OUT_RATIO = 0.3e18;

    // Note that all t values (not tp or tpp) could consist of uint's, as could all Params. But it's complicated to
    // convert all the time, so we make them all signed. We also store all intermediate values signed. An exception are
    // the functions that are used by the contract b/c there the values are stored unsigned.
    struct Params {
        // Price bounds (lower and upper). 0 < alpha < beta
        int256 alpha;
        int256 beta;
        // Rotation vector:
        // phi in (-90 degrees, 0] is the implicit rotation vector. It's stored as a point:
        int256 c; // c = cos(-phi) >= 0. rounded to 18 decimals
        int256 s; //  s = sin(-phi) >= 0. rounded to 18 decimals
        // Invariant: c^2 + s^2 == 1, i.e., the point (c, s) is normalized.
        // due to rounding, this may not = 1. The term dSq in DerivedParams corrects for this in extra precision

        // Stretching factor:
        int256 lambda; // lambda >= 1 where lambda == 1 is the circle.
    }

    // terms in this struct are stored in extra precision (38 decimals) with final decimal rounded down
    struct DerivedParams {
        Vector2 tauAlpha;
        Vector2 tauBeta;
        int256 u; // from (A chi)_y = lambda * u + v
        int256 v; // from (A chi)_y = lambda * u + v
        int256 w; // from (A chi)_x = w / lambda + z
        int256 z; // from (A chi)_x = w / lambda + z
        int256 dSq; // error in c^2 + s^2 = dSq, used to correct errors in c, s, tau, u,v,w,z calculations
        //int256 dAlpha; // normalization constant for tau(alpha)
        //int256 dBeta; // normalization constant for tau(beta)
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

    function scalarProd(Vector2 memory t1, Vector2 memory t2) internal pure returns (int256 ret) {
        // TODO LEAVE IN CHECKS HERE! DO NOTHING (except for removing this comment when done)!
        ret = t1.x.mulDownMag(t2.x).add(t1.y.mulDownMag(t2.y));
    }

    // "Methods" for Params. We could put these into a separate library and import them via 'using' to get method call
    // syntax.

    /** @dev Calculate A t where A is given in Section 2.2
     *  This is reversing rotation and scaling of the ellipse (mapping back to circle) */
    function mulA(Params memory params, Vector2 memory tp) internal pure returns (Vector2 memory t) {
        // TODO OK TO REMOVE CHECKS GIVEN CONDITIONS ON […]
        // NB: This function is only used inside calculatePrice(). This is why we can make two simplifications:
        // 1. We don't correct for precision of s, c using d.dSq because that level of precision is not important in this context.
        // 2. We don't need to check for over/underflow b/c these are impossible in that context and given the (checked) assumptions on the various values.
        t.x = params.c.mulDownMag(tp.x).divDownMag(params.lambda).sub(params.s.mulDownMag(tp.y).divDownMag(params.lambda));
        t.y = params.s.mulDownMag(tp.x).add(params.c.mulDownMag(tp.y));
    }

    /** @dev Given price px on the transformed ellipse, get the untransformed price pxc on the circle
     *  px = price of asset x in terms of asset y.
     *  See Definition 1 in Section 2.1.1 */
    function zeta(Params memory params, int256 px) internal pure returns (int256 pxc) {
        Vector2 memory nd = mulA(params, Vector2(-SignedFixedPoint.ONE, px));
        return -nd.y.divDownMag(nd.x);
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

    // function tauXp(
    //     Params memory p,
    //     int256 px,
    //     int256 dPx
    // ) internal pure returns (Vector2 memory tauPx) {
    //     // these shouldn't overflow b/c extra precision products should be <= 1
    //     // (c px - s)*dPx
    //     tauPx.x = ((px * 1e20).mulDown(p.c) - p.s * 1e20).mulXp(dPx);
    //     // (c + s px)*dPx / lambda
    //     tauPx.y = ((px * 1e20).mulDown(p.s) + p.c * 1e20).divDown(p.lambda).mulXp(dPx);
    // }

    /// make derived params in extra precision, intentionally missing a factor of 1/d where s^2 + c^2 = d^2
    /// TODO: note how much error could happen in last place for under/overestimate purposes
    // function mkDerivedParamsXp(Params memory p) internal pure returns (DerivedParams memory d) {
    //     d.tauAlpha = tauXp(p, p.alpha, p.dAlpha);
    //     d.tauBeta = tauXp(p, p.beta, p.dBeta);
    //     // w = sc (tau(beta)_y - tau(alpha)_y
    //     d.w = (p.s * 1e20).mulDown(p.c).mulXp(d.tauBeta.y.sub(d.tauAlpha.y));
    //     // z = c^2 tau(beta)_x + s^2 tau(alpha)_x
    //     d.z = (p.c * 1e20).mulDown(p.c).mulXp(d.tauBeta.x);
    //     d.z = d.z.add((p.s * 1e20)).mulDown(p.s).mulXp(d.tauAlpha.x);
    //     // u = sc (tau(beta)_x - tau(alpha)_x)
    //     d.u = (p.s * 1e20).mulDown(p.c).mulXp(d.tauBeta.x.sub(d.tauAlpha.x));
    //     // v = s^2 tau(beta)_y + c^2 tau(alpha)_y
    //     d.v = (p.s * 1e20).mulDown(p.s).mulXp(d.tauBeta.y);
    //     d.v = d.v.add((p.c * 1e20).mulDown(p.c).mulXp(d.tauAlpha.y));
    // }

    /** @dev Given price on a circle, gives the normalized corresponding point on the circle centered at the origin
     *  pxc = price of asset x in terms of asset y (measured on the circle)
     *  Notice that the eta function does not depend on Params.
     *  See Definition 2 in Section 2.1.1 */
    function eta(int256 pxc) internal pure returns (Vector2 memory tpp) {
        int256 z = GyroPoolMath._sqrt(FixedPoint.ONE.add(uint256(pxc.mulDownMag(pxc))), 5).toInt256();
        tpp = eta(pxc, z);
    }

    /** @dev Calculates eta in more efficient way if the square root is known and input as second arg */
    function eta(int256 pxc, int256 z) internal pure returns (Vector2 memory tpp) {
        tpp.x = pxc.divDownMag(z);
        tpp.y = SignedFixedPoint.ONE.divDownMag(z);
    }

    /** @dev Calculate virtual offset a given invariant r.
     *  See calculation in Section 2.1.2 Computing reserve offsets
     *  Note that, in contrast to virtual reserve offsets in CPMM, these are *subtracted* from the real
     *  reserves, moving the curve to the upper-right. They can be positive or negative, but not both can be negative.
     *  Calculates a = r*(A^{-1}tau(beta))_x rounding up in signed direction
     *  Notice that error in r is scaled by lambda, and so rounding direction is important */
    function virtualOffset0(
        Params memory p,
        DerivedParams memory d,
        Vector2 memory r // overestimate in x component, underestimate in y
    ) internal pure returns (int256 a) {
        // TODO OK TO REMOVE CHECKS GIVEN CONDITIONS ON r * lambda
        // a = r lambda c tau(beta)_x + rs tau(beta)_y
        //       account for 1 factors of dSq (2 s,c factors)
        int256 termXp = d.tauBeta.x.divXp(d.dSq);
        a = d.tauBeta.x > 0 ? r.x.mulUpMag(p.lambda).mulUpMag(p.c).mulUpXpToNp(termXp) : r.y.mulDownMag(p.lambda).mulDownMag(p.c).mulUpXpToNp(termXp);

        // use fact that tau(beta)_y > 0, so the required rounding direction is clear.
        a = a.add(r.x.mulUpMag(p.s).mulUpXpToNp(d.tauBeta.y.divXp(d.dSq)));
    }

    /** @dev calculate virtual offset b given invariant r.
     *  Calculates b = r*(A^{-1}tau(alpha))_y rounding up in signed direction */
    function virtualOffset1(
        Params memory p,
        DerivedParams memory d,
        Vector2 memory r // overestimate in x component, underestimate in y
    ) internal pure returns (int256 b) {
        // TODO OK TO REMOVE CHECKS GIVEN CONDITIONS ON r * lambda
        // b = -r \lambda s tau(alpha)_x + rc tau(alpha)_y
        //       account for 1 factors of dSq (2 s,c factors)
        int256 termXp = d.tauAlpha.x.divXp(d.dSq);
        b = (d.tauAlpha.x < 0) ? r.x.mulUpMag(p.lambda).mulUpMag(p.s).mulUpXpToNp(-termXp) : (-r.y).mulDownMag(p.lambda).mulDownMag(p.s).mulUpXpToNp(termXp);

        // use fact that tau(alpha)_y > 0, so the required rounding direction is clear.
        b = b.add(r.x.mulUpMag(p.c).mulUpXpToNp(d.tauAlpha.y.divXp(d.dSq)));
    }

    /** Maximal value for the real reserves x when the respective other balance is 0 for given invariant
     *  See calculation in Section 2.1.2. Calculation is ordered here for precision, but erorr in r is magnified by lambda
     *  Rounds down in signed direction */
    function maxBalances0(
        Params memory p,
        DerivedParams memory d,
        Vector2 memory r // overestimate in x-component, underestimate in y-component
    ) internal pure returns (int256 xp) {
        // TODO OK TO REMOVE CHECKS GIVEN CONDITIONS ON r * lambda
        // x^+ = r lambda c (tau(beta)_x - tau(alpha)_x) + rs (tau(beta)_y - tau(alpha)_y)
        //      account for 1 factors of dSq (2 s,c factors)
        int256 termXp1 = (d.tauBeta.x.sub(d.tauAlpha.x)).divXp(d.dSq); // note tauBeta.x > tauAlpha.x, so this is > 0 and rounding direction is clear
        int256 termXp2 = (d.tauBeta.y.sub(d.tauAlpha.y)).divXp(d.dSq); // note this may be negative, but since tauBeta.y, tauAlpha.y >= 0, it is always in [-1, 1].
        xp = r.y.mulDownMag(p.lambda).mulDownMag(p.c).mulDownXpToNp(termXp1);
        xp = xp.add((termXp2 > 0 ? r.y.mulDownMag(p.s) : r.x.mulUpMag(p.s)).mulDownXpToNp(termXp2));
    }

    /** Maximal value for the real reserves y when the respective other balance is 0 for given invariant
     *  See calculation in Section 2.1.2. Calculation is ordered here for precision, but erorr in r is magnified by lambda
     *  Rounds down in signed direction */
    function maxBalances1(
        Params memory p,
        DerivedParams memory d,
        Vector2 memory r // overestimate in x-component, underestimate in y-component
    ) internal pure returns (int256 yp) {
        // TODO OK TO REMOVE CHECKS GIVEN CONDITIONS ON r * lambda
        // y^+ = r lambda s (tau(beta)_x - tau(alpha)_x) + rc (tau(alpha)_y - tau(beta)_y)
        //      account for 1 factors of dSq (2 s,c factors)
        int256 termXp1 = (d.tauBeta.x.sub(d.tauAlpha.x)).divXp(d.dSq); // note tauBeta.x > tauAlpha.x
        int256 termXp2 = (d.tauAlpha.y.sub(d.tauBeta.y)).divXp(d.dSq);
        yp = r.y.mulDownMag(p.lambda).mulDownMag(p.s).mulDownXpToNp(termXp1);
        yp = yp.add((termXp2 > 0 ? r.y.mulDownMag(p.c) : r.x.mulUpMag(p.c)).mulDownXpToNp(termXp2));
    }

    /** @dev Compute the invariant 'r' corresponding to the given values. The invariant can't be negative, but
     *  we use a signed value to store it because all the other calculations are happening with signed ints, too.
     *  Computes r according to Prop 13 in 2.2.1 Initialization from Real Reserves
     *  orders operations to achieve best precision
     *  Returns an underestimate and a bound on error size */
    function calculateInvariantWithError(
        uint256[] memory balances,
        Params memory params,
        DerivedParams memory derived
    ) internal pure returns (int256, int256) {
        (int256 x, int256 y) = (balances[0].toInt256(), balances[1].toInt256());
        int256 AtAChi = calcAtAChi(x, y, params, derived);
        (int256 sqrt, int256 err) = calcInvariantSqrt(x, y, params, derived);
        // calculate the error in the square root term, separates cases based on sqrt >= 1/2
        // somedayTODO: can this be improved for cases of large balances (when xp error magnifies to np)
        // Note: the minimum non-zero value of sqrt is 1e-9 since the minimum argument is 1e-18
        if (sqrt > 0) {
            // err + 1 to account for O(eps_np) term ignored before
            err = (err + 1).divUpMag(2 * sqrt);
        } else {
            // in the false case here, the extra precision error does not magnify, and so the error inside the sqrt is O(1e-18)
            // somedayTODO: The true case will almost surely never happen (can it be removed)
            err = err > 0 ? GyroPoolMath._sqrt(err.toUint256(), 5).toInt256() : 1e9;
        }
        // calculate the error in the numerator, scale the error by 20 to be sure all possible terms accounted for
        err = ((params.lambda.mulUpMag(x.add(y)) / ONE_XP).add(err) + 1) * 20;

        // A chi \cdot A chi > 1, so round it up to round denominator up
        // denominator uses extra precision, so we do * 1/denominator so we are sure the calculation doesn't overflow
        int256 mulDenominator = ONE_XP.divXp(calcAChiAChiInXp(params, derived).sub(ONE_XP));
        // as alternative, could do, but could overflow: invariant = (AtAChi.add(sqrt) - err).divXp(denominator);
        int256 invariant = (AtAChi.add(sqrt) - err).mulDownXpToNp(mulDenominator);
        // error scales if denominator is small
        // NB: This error calculation computes the error in the expression "numerator / denominator", but in this code
        // we actually use the formula "numerator * (1 / denominator)" to compute the invariant. This affects this line
        // and the one below.
        err = err.mulUpXpToNp(mulDenominator);
        // account for relative error due to error in the denominator
        // error in denominator is O(epsilon) if lambda<1e11, scale up by 10 to be sure we catch it, and add O(eps)
        // error in denominator is lambda^2 * 2e-37 and scales relative to the result / denominator
        // Scale by a constant to account for errors in the scaling factor itself and limited compounding.
        // calculating lambda^2 w/o decimals so that the calculation will never overflow, the lost precision isn't important
        err = err + ((invariant.mulUpXpToNp(mulDenominator) * ((params.lambda * params.lambda) / 1e36)) * 40) / ONE_XP + 1;
        return (invariant, err);
    }

    function calculateInvariant(
        uint256[] memory balances,
        Params memory params,
        DerivedParams memory derived
    ) internal pure returns (uint256 uinvariant) {
        (int256 invariant, ) = calculateInvariantWithError(balances, params, derived);
        uinvariant = invariant.toUint256();
    }

    /// @dev calculate At \cdot A chi, ignores rounding direction. We will later compensate for the rounding error.
    function calcAtAChi(
        int256 x,
        int256 y,
        Params memory p,
        DerivedParams memory d
    ) internal pure returns (int256 val) {
        // TODO OK TO REMOVE CHECKS GIVEN CONDITIONS ON (x + y) * lambda
        // (cx - sy) * (w/lambda + z) / lambda
        //      account for 2 factors of dSq (4 s,c factors)
        int256 termXp = (d.w.divDownMag(p.lambda).add(d.z)).divDownMag(p.lambda).divXp(d.dSq).divXp(d.dSq);
        val = (x.mulDownMag(p.c).sub(y.mulDownMag(p.s))).mulDownXpToNp(termXp);

        // (x lambda s + y lambda c) * u, note u > 0
        int256 termNp = x.mulDownMag(p.lambda).mulDownMag(p.s).add(y.mulDownMag(p.lambda).mulDownMag(p.c));
        val = val.add(termNp.mulDownXpToNp(d.u.divXp(d.dSq).divXp(d.dSq)));

        // (sx+cy) * v, note v > 0
        termNp = x.mulDownMag(p.s).add(y.mulDownMag(p.c));
        val = val.add(termNp.mulDownXpToNp(d.v.divXp(d.dSq).divXp(d.dSq)));
    }

    /// @dev calculates A chi \cdot A chi in extra precision
    /// Note: this can be >1 (and involves factor of lambda^2). We can compute it in extra precision w/o overflowing b/c it will be
    /// at most 38 + 16 digits (38 from decimals, 2*8 from lambda^2 if lambda=1e8)
    /// Since we will only divide by this later, we will not need to worry about overflow in that operation if done in the right way
    /// TODO: is rounding direction ok?
    function calcAChiAChiInXp(Params memory p, DerivedParams memory d) internal pure returns (int256 val) {
        // TODO OK TO REMOVE CHECKS GIVEN CONDITIONS ON lambda.
        // (A chi)_y^2 = lambda^2 u^2 + lambda 2 u v + v^2
        //      account for 3 factors of dSq (6 s,c factors)
        // SOMEDAY: In these calcs, a calculated value is multiplied by lambda and lambda^2, resp, which implies some
        // error amplification. It's fine b/c we're doing it in extra precision here, but would still be nice if it
        // could be avoided, perhaps by splitting up the numbers into a high and low part.
        val = p.lambda.mulUpMag((2 * d.u).mulXp(d.v).divXp(d.dSq).divXp(d.dSq).divXp(d.dSq));
        // for lambda^2 u^2 factor in rounding error in u since lambda could be big
        // Note: lambda^2 is multiplied at the end to be sure the calculation doesn't overflow, but this can lose some precision
        val = val.add(((d.u + 1).mulXp(d.u + 1).divXp(d.dSq).divXp(d.dSq).divXp(d.dSq)).mulUpMag(p.lambda).mulUpMag(p.lambda));
        // the next line converts from extre precision to normal precision post-computation while rounding up
        val = val.add((d.v).mulXp(d.v).divXp(d.dSq).divXp(d.dSq).divXp(d.dSq));

        // (A chi)_x^2 = (w/lambda + z)^2
        //      account for 3 factors of dSq (6 s,c factors)
        int256 termXp = d.w.divUpMag(p.lambda).add(d.z);
        val = val.add(termXp.mulXp(termXp).divXp(d.dSq).divXp(d.dSq).divXp(d.dSq));
    }

    /// @dev calculate -(At)_x ^2 (A chi)_y ^2 + (At)_x ^2, rounding down in signed direction
    function calcMinAtxAChiySqPlusAtxSq(
        int256 x,
        int256 y,
        Params memory p,
        DerivedParams memory d
    ) internal pure returns (int256 val) {
        ////////////////////////////////////////////////////////////////////////////////////
        // (At)_x^2 (A chi)_y^2 = (x^2 c^2 - xy2sc + y^2 s^2) (u^2 + 2uv/lambda + v^2/lambda^2)
        //      account for 4 factors of dSq (8 s,c factors)
        //
        // (At)_x^2 = (x^2 c^2 - xy2sc + y^2 s^2)/lambda^2
        //      account for 1 factor of dSq (2 s,c factors)
        ////////////////////////////////////////////////////////////////////////////////////
        // TODO OK TO REMOVE CHECKS GIVEN CONDITIONS ON (x + y)^2
        int256 termNp = x.mulUpMag(x).mulUpMag(p.c).mulUpMag(p.c).add(y.mulUpMag(y).mulUpMag(p.s).mulUpMag(p.s));
        termNp = termNp.sub(x.mulDownMag(y).mulDownMag(p.c * 2).mulDownMag(p.s));

        int256 termXp = d.u.mulXp(d.u).add((2 * d.u).mulXp(d.v).divDownMag(p.lambda)).add(d.v.mulXp(d.v).divDownMag(p.lambda).divDownMag(p.lambda));
        termXp = termXp.divXp(d.dSq).divXp(d.dSq).divXp(d.dSq).divXp(d.dSq);
        val = (-termNp).mulDownXpToNp(termXp);

        // now calculate (At)_x^2 accounting for possible rounding error to round down
        // need to do 1/dSq in a way so that there is no overflow for large balances
        val = val.add((termNp - 9).divDownMag(p.lambda).divDownMag(p.lambda).mulDownXpToNp(SignedFixedPoint.ONE_XP.divXp(d.dSq)));
    }

    /// @dev calculate 2(At)_x * (At)_y * (A chi)_x * (A chi)_y, ignores rounding direction
    //  Note: this ignores rounding direction and is corrected for later
    function calc2AtxAtyAChixAChiy(
        int256 x,
        int256 y,
        Params memory p,
        DerivedParams memory d
    ) internal pure returns (int256 val) {
        ////////////////////////////////////////////////////////////////////////////////////
        // = ((x^2 - y^2)sc + yx(c^2-s^2)) * 2 * (zu + (wu + zv)/lambda + wv/lambda^2)
        //      account for 4 factors of dSq (8 s,c factors)
        ////////////////////////////////////////////////////////////////////////////////////
        // TODO OK TO REMOVE CHECKS GIVEN CONDITIONS ON (x + y)^2
        int256 termNp = (x.mulDownMag(x).sub(y.mulUpMag(y))).mulDownMag(2 * p.c).mulDownMag(p.s);
        int256 xy = y.mulDownMag(2 * x);
        termNp = termNp.add(xy.mulDownMag(p.c).mulDownMag(p.c)).sub(xy.mulDownMag(p.s).mulDownMag(p.s));

        int256 termXp = d.z.mulXp(d.u).add(d.w.mulXp(d.v).divDownMag(p.lambda).divDownMag(p.lambda));
        termXp = termXp.add((d.w.mulXp(d.u).add(d.z.mulXp(d.v))).divDownMag(p.lambda));
        termXp = termXp.divXp(d.dSq).divXp(d.dSq).divXp(d.dSq).divXp(d.dSq);

        val = termNp.mulDownXpToNp(termXp);
    }

    /// @dev calculate -(At)_y ^2 (A chi)_x ^2 + (At)_y ^2, rounding down in signed direction
    function calcMinAtyAChixSqPlusAtySq(
        int256 x,
        int256 y,
        Params memory p,
        DerivedParams memory d
    ) internal pure returns (int256 val) {
        ////////////////////////////////////////////////////////////////////////////////////
        // (At)_y^2 (A chi)_x^2 = (x^2 s^2 + xy2sc + y^2 c^2) * (z^2 + 2zw/lambda + w^2/lambda^2)
        //      account for 4 factors of dSq (8 s,c factors)
        // (At)_y^2 = (x^2 s^2 + xy2sc + y^2 c^2)
        //      account for 1 factor of dSq (2 s,c factors)
        ////////////////////////////////////////////////////////////////////////////////////
        // TODO OK TO REMOVE CHECKS GIVEN CONDITIONS ON (x + y)^2
        int256 termNp = x.mulUpMag(x).mulUpMag(p.s).mulUpMag(p.s).add(y.mulUpMag(y).mulUpMag(p.c).mulUpMag(p.c));
        termNp = termNp.add(x.mulUpMag(y).mulUpMag(p.s * 2).mulUpMag(p.c));

        int256 termXp = d.z.mulXp(d.z).add(d.w.mulXp(d.w).divDownMag(p.lambda).divDownMag(p.lambda));
        termXp = termXp.add((2 * d.z).mulXp(d.w).divDownMag(p.lambda));
        termXp = termXp.divXp(d.dSq).divXp(d.dSq).divXp(d.dSq).divXp(d.dSq);
        val = (-termNp).mulDownXpToNp(termXp);

        // now calculate (At)_y^2 accounting for possible rounding error to round down
        // need to do 1/dSq in a way so that there is no overflow for large balances
        val = val.add((termNp - 9).mulDownXpToNp(SignedFixedPoint.ONE_XP.divXp(d.dSq)));
    }

    /// @dev Rounds down. Also returns an estimate for the error of the term under the sqrt (!) and without the regular
    /// normal-precision error of O(1e-18).
    function calcInvariantSqrt(
        int256 x,
        int256 y,
        Params memory p,
        DerivedParams memory d
    ) internal pure returns (int256 val, int256 err) {
        // TODO OK TO REMOVE CHECKS GIVEN CONDITIONS FROM THE OTHER FUNCTIONS (on (x + y)^2 specifically)
        val = calcMinAtxAChiySqPlusAtxSq(x, y, p, d).add(calc2AtxAtyAChixAChiy(x, y, p, d));
        val = val.add(calcMinAtyAChixSqPlusAtySq(x, y, p, d));
        // error inside the square root is O((x^2 + y^2) * eps_xp) + O(eps_np), where eps_xp=1e-38, eps_np=1e-18
        // note that in terms of rounding down, error corrects for calc2AtxAtyAChixAChiy()
        // however, we also use this error to correct the invariant for an overestimate in swaps, it is all the same order though
        // Note the O(eps_np) term will be dealt with later, so not included yet
        // Note that the extra precision term doesn't propagate unless balances are > 100b
        err = (x.mulUpMag(x).add(y.mulUpMag(y))) / 1e38;
        // we will account for the error later after the square root
        // mathematically, terms in square root > 0, so treat as 0 if it is < 0 b/c of rounding error
        val = val > 0 ? GyroPoolMath._sqrt(val.toUint256(), 5).toInt256() : 0;
    }

    /** @dev Instantanteous price.
     *  See Prop. 12 in 2.1.6 Computing Prices */
    function calculatePrice(
        uint256[] memory balances,
        Params memory params,
        DerivedParams memory derived,
        int256 invariant
    ) internal pure returns (uint256 px) {
        // TODO OK TO REMOVE CHECKS GIVEN CONDITIONS ON […] EXCEPT FOR THE ONES MARKED
        // shift by virtual offsets to get v(t)
        Vector2 memory r = Vector2(invariant, invariant); // ignore r rounding for spot price, precision will be lost in TWAP anyway
        Vector2 memory ab = Vector2(virtualOffset0(params, derived, r), virtualOffset1(params, derived, r));
        Vector2 memory vec = Vector2(balances[0].toInt256().sub(ab.x), balances[1].toInt256().sub(ab.y));

        // transform to circle to get Av(t)
        vec = mulA(params, vec);
        // compute prices on circle
        Vector2 memory pc = Vector2(vec.x.divDownMag(vec.y), ONE);

        // Convert prices back to ellipse
        // NB: These operations check for overflow because the price pc[0] might be large when vex.y is small.
        // SOMEDAY I think this probably can't actually happen due to our bounds on the different values. In this case we could do this unchecked as well.
        int256 pgx = scalarProd(pc, mulA(params, Vector2(ONE, 0)));
        // TODO LEAVE IN THIS CHECK, then delete this comment when done.
        px = pgx.divDownMag(scalarProd(pc, mulA(params, Vector2(0, ONE)))).toUint256();
    }

    /** @dev Check that post-swap balances obey maximal asset bounds
     *  newBalance = post-swap balance of one asset
     *  assetIndex gives the index of the provided asset (0 = X, 1 = Y) */
    function checkAssetBounds(
        Params memory params,
        DerivedParams memory derived,
        Vector2 memory invariant,
        int256 newBal,
        uint8 assetIndex
    ) internal pure {
        if (assetIndex == 0) {
            int256 xPlus = maxBalances0(params, derived, invariant);
            _require(newBal <= xPlus, GyroCEMMPoolErrors.ASSET_BOUNDS_EXCEEDED);
        } else {
            int256 yPlus = maxBalances1(params, derived, invariant);
            _require(newBal <= yPlus, GyroCEMMPoolErrors.ASSET_BOUNDS_EXCEEDED);
        }
    }

    function calcOutGivenIn(
        uint256[] memory balances,
        uint256 amountIn,
        bool tokenInIsToken0,
        Params memory params,
        DerivedParams memory derived,
        Vector2 memory invariant
    ) internal pure returns (uint256 amountOut) {
        function(int256, Params memory, DerivedParams memory, Vector2 memory) pure returns (int256) calcGiven;
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
        // TODO OK TO REMOVE CHECKS GIVEN CONDITIONS ON […]

        _require(amountIn <= balances[ixIn].mulDown(_MAX_IN_RATIO), Errors.MAX_IN_RATIO);
        int256 balInNew = balances[ixIn].add(amountIn).toInt256();
        checkAssetBounds(params, derived, invariant, balInNew, ixIn);
        int256 balOutNew = calcGiven(balInNew, params, derived, invariant);
        uint256 assetBoundError = GyroCEMMPoolErrors.ASSET_BOUNDS_EXCEEDED;
        _require(balOutNew.toUint256() < balances[ixOut], assetBoundError);
        amountOut = balances[ixOut].sub(balOutNew.toUint256());
        _require(amountOut <= balances[ixOut].mulDown(_MAX_OUT_RATIO), Errors.MAX_OUT_RATIO);
    }

    function calcInGivenOut(
        uint256[] memory balances,
        uint256 amountOut,
        bool tokenInIsToken0,
        Params memory params,
        DerivedParams memory derived,
        Vector2 memory invariant
    ) internal pure returns (uint256 amountIn) {
        function(int256, Params memory, DerivedParams memory, Vector2 memory) pure returns (int256) calcGiven;
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
        // TODO OK TO REMOVE CHECKS GIVEN CONDITIONS ON […]

        _require(amountOut <= balances[ixOut].mulDown(_MAX_OUT_RATIO), Errors.MAX_OUT_RATIO);
        int256 balOutNew = balances[ixOut].sub(amountOut).toInt256();
        int256 balInNew = calcGiven(balOutNew, params, derived, invariant);
        uint256 assetBoundError = GyroCEMMPoolErrors.ASSET_BOUNDS_EXCEEDED;
        _require(balInNew.toUint256() > balances[ixIn], assetBoundError);
        checkAssetBounds(params, derived, invariant, balInNew, ixIn);
        amountIn = balInNew.toUint256().sub(balances[ixIn]);
        _require(amountIn <= balances[ixIn].mulDown(_MAX_IN_RATIO), Errors.MAX_IN_RATIO);
    }

    /** @dev Variables are named for calculating y given x
     *  to calculate x given y, change x->y, s->c, c->s, a_>b, b->a, tauBeta.x -> -tauAlpha.x, tauBeta.y -> tauAlpha.y
     *  calculates an overestimate of calculated reserve post-swap */
    function solveQuadraticSwap(
        int256 lambda,
        int256 x,
        int256 s,
        int256 c,
        Vector2 memory r, // overestimate in x component, underestimate in y
        Vector2 memory ab,
        Vector2 memory tauBeta,
        int256 dSq
    ) internal pure returns (int256) {
        // x component will round up, y will round down, use extra precision
        // TODO OK TO REMOVE CHECKS GIVEN CONDITIONS ON […]
        Vector2 memory lamBar;
        lamBar.x = SignedFixedPoint.ONE_XP.sub(SignedFixedPoint.ONE_XP.divDownMag(lambda).divDownMag(lambda));
        // Note: The following cannot become negative even with errors because we require lambda >= 1 and
        // divUpMag returns the exact result if the quotient is representable in 18 decimals.
        lamBar.y = SignedFixedPoint.ONE_XP.sub(SignedFixedPoint.ONE_XP.divUpMag(lambda).divUpMag(lambda));
        // using qparams struct to avoid "stack too deep"
        QParams memory q;
        // shift by the virtual offsets
        // note that we want an overestimate of offset here so that -x'*lambar*s*c is overestimated in signed direction
        // account for 1 factor of dSq (2 s,c factors)
        int256 xp = x.sub(ab.x);
        if (xp > 0) {
            q.b = (-xp).mulDownMag(s).mulDownMag(c).mulUpXpToNp(lamBar.y.divXp(dSq));
        } else {
            q.b = (-xp).mulUpMag(s).mulUpMag(c).mulUpXpToNp(lamBar.x.divXp(dSq) + 1);
        }

        // x component will round up, y will round down, use extra precision
        // account for 1 factor of dSq (2 s,c factors)
        Vector2 memory sTerm;
        // we wil take sTerm = 1 - sTerm below, using multiple lines to avoid "stack too deep"
        sTerm.x = lamBar.y.mulDownMag(s).mulDownMag(s).divXp(dSq);
        sTerm.y = lamBar.x.mulUpMag(s).mulUpMag(s).divXp(dSq + 1) + 1; // account for rounding error in dSq, divXp
        sTerm = Vector2(SignedFixedPoint.ONE_XP.sub(sTerm.x), SignedFixedPoint.ONE_XP.sub(sTerm.y));
        // ^^ NB: The components of sTerm are non-negative: We only need to worry about sTerm.y. This is non-negative b/c, because of bounds on lambda lamBar <= 1 - 1e-16, and division by dSq ensures we have enough precision so that rounding errors are never magnitude 1e-16.

        // now compute the argument of the square root
        q.c = -calcXpXpDivLambdaLambda(x, r, lambda, s, c, tauBeta, dSq);
        q.c = q.c.add(r.y.mulDownMag(r.y).mulDownXpToNp(sTerm.y));
        // the square root is always being subtracted, so round it down to overestimate the end balance
        // mathematically, terms in square root > 0, so treat as 0 if it is < 0 b/c of rounding error
        q.c = q.c > 0 ? GyroPoolMath._sqrt(q.c.toUint256(), 5).toInt256() : 0;

        // calculate the result in q.a
        if (q.b - q.c > 0) {
            q.a = (q.b.sub(q.c)).mulUpXpToNp(SignedFixedPoint.ONE_XP.divXp(sTerm.y) + 1);
        } else {
            q.a = (q.b.sub(q.c)).mulUpXpToNp(SignedFixedPoint.ONE_XP.divXp(sTerm.x));
        }

        // lastly, add the offset, note that we want an overestimate of offset here
        return q.a.add(ab.y);
    }

    /** @dev Calculates x'x'/λ^2 where x' = x - b = x - r (A^{-1}tau(beta))_x
     *  calculates an overestimate
     *  to calculate y'y', change x->y, s->c, c->s, tauBeta.x -> -tauAlpha.x, tauBeta.y -> tauAlpha.y  */
    function calcXpXpDivLambdaLambda(
        int256 x,
        Vector2 memory r, // overestimate in x component, underestimate in y
        int256 lambda,
        int256 s,
        int256 c,
        Vector2 memory tauBeta,
        int256 dSq
    ) internal pure returns (int256) {
        // TODO OK TO REMOVE CHECKS GIVEN CONDITIONS ON […]
//////////////////////////////////////////////////////////////////////////////////
        // x'x'/lambda^2 = r^2 c^2 tau(beta)_x^2
        //      + ( r^2 2s c tau(beta)_x tau(beta)_y - rx 2c tau(beta)_x ) / lambda
        //      + ( r^2 s^2 tau(beta)_y^2 - rx 2s tau(beta)_y + x^2 ) / lambda^2
        //////////////////////////////////////////////////////////////////////////////////
        QParams memory q; // for working terms
        // q.a = r^2 s 2c tau(beta)_x tau(beta)_y
        //      account for 2 factors of dSq (4 s,c factors)
        int256 termXp = tauBeta.x.mulXp(tauBeta.y).divXp(dSq).divXp(dSq);
        if (termXp > 0) {
            q.a = r.x.mulUpMag(r.x).mulUpMag(2 * s);
            q.a = q.a.mulUpMag(c).mulUpXpToNp(termXp + 7); // +7 account for rounding in termXp
        } else {
            q.a = r.y.mulDownMag(r.y).mulDownMag(2 * s);
            q.a = q.a.mulDownMag(c).mulUpXpToNp(termXp);
        }

        // -rx 2c tau(beta)_x
        //      account for 1 factor of dSq (2 s,c factors)
        if (tauBeta.x < 0) {
            // +3 account for rounding in extra precision terms
            q.b = r.x.mulUpMag(x).mulUpMag(2 * c).mulUpXpToNp(-tauBeta.x.divXp(dSq) + 3);
        } else {
            q.b = (-r.y).mulDownMag(x).mulDownMag(2 * c).mulUpXpToNp(tauBeta.x.divXp(dSq));
        }
        // q.a later needs to be divided by lambda
        q.a = q.a.add(q.b);

        // q.b = r^2 s^2 tau(beta)_y^2
        //      account for 2 factors of dSq (4 s,c factors)
        termXp = tauBeta.y.mulXp(tauBeta.y).divXp(dSq).divXp(dSq) + 7; // +7 account for rounding in termXp
        q.b = r.x.mulUpMag(r.x).mulUpMag(s);
        q.b = q.b.mulUpMag(s).mulUpXpToNp(termXp);

        // q.c = -rx 2s tau(beta)_y, recall that tauBeta.y > 0 so round lower in magnitude
        //      account for 1 factor of dSq (2 s,c factors)
        q.c = (-r.y).mulDownMag(x).mulDownMag(2 * s).mulUpXpToNp(tauBeta.y.divXp(dSq));

        // (q.b + q.c + x^2) / lambda
        q.b = q.b.add(q.c).add(x.mulUpMag(x));
        q.b = q.b > 0 ? q.b.divUpMag(lambda) : q.b.divDownMag(lambda);

        // remaining calculation is (q.a + q.b) / lambda
        q.a = q.a.add(q.b);
        q.a = q.a > 0 ? q.a.divUpMag(lambda) : q.a.divDownMag(lambda);

        // + r^2 c^2 tau(beta)_x^2
        //      account for 2 factors of dSq (4 s,c factors)
        termXp = tauBeta.x.mulXp(tauBeta.x).divXp(dSq).divXp(dSq) + 7; // +7 account for rounding in termXp
        int256 val = r.x.mulUpMag(r.x).mulUpMag(c).mulUpMag(c);
        return (val.mulUpXpToNp(termXp)).add(q.a);
    }

    /** @dev compute y such that (x, y) satisfy the invariant at the given parameters.
     *  Note that we calculate an overestimate of y
     *   See Prop 14 in section 2.2.2 Trade Execution */
    function calcYGivenX(
        int256 x,
        Params memory params,
        DerivedParams memory d,
        Vector2 memory r // overestimate in x component, underestimate in y
    ) internal pure returns (int256 y) {
        // want to overestimate the virtual offsets except in a particular setting that will be corrected for later
        // note that the error correction in the invariant should more than make up for uncaught rounding directions (in 38 decimals) in virtual offsets
        Vector2 memory ab = Vector2(virtualOffset0(params, d, r), virtualOffset1(params, d, r));
        y = solveQuadraticSwap(params.lambda, x, params.s, params.c, r, ab, d.tauBeta, d.dSq);
    }

    function calcXGivenY(
        int256 y,
        Params memory params,
        DerivedParams memory d,
        Vector2 memory r // overestimate in x component, underestimate in y
    ) internal pure returns (int256 x) {
        // want to overestimate the virtual offsets except in a particular setting that will be corrected for later
        // note that the error correction in the invariant should more than make up for uncaught rounding directions (in 38 decimals) in virtual offsets
        Vector2 memory ba = Vector2(virtualOffset1(params, d, r), virtualOffset0(params, d, r));
        // change x->y, s->c, c->s, b->a, a->b, tauBeta.x -> -tauAlpha.x, tauBeta.y -> tauAlpha.y vs calcYGivenX
        x = solveQuadraticSwap(params.lambda, y, params.c, params.s, r, ba, Vector2(-d.tauAlpha.x, d.tauAlpha.y), d.dSq);
    }
}
