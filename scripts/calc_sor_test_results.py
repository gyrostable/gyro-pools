from pprint import pprint

from brownie import *
from brownie.exceptions import VirtualMachineError

from tests.support.quantized_decimal import QuantizedDecimal as D
from tests.support.types import ECLPMathParams
from tests.support.utils import scale, unscale

from tests.geclp import eclp_prec_implementation
from tests.geclp import eclp_derivatives

gyro_two_math_testing = accounts[0].deploy(Gyro2CLPMathTesting)
gyro_three_math_testing = accounts[0].deploy(Gyro3CLPMathTesting)

LIMIT_AMOUNT_IN_BUFFER_FACTOR = D("0.999999000000000000")


def calc_eclp_test_results():
    params = ECLPMathParams(
        alpha=D("0.050000000000020290"),
        beta=D("0.397316269897841178"),
        c=D("0.9551573261744535"),
        s=D("0.29609877111408056"),
        l=D("748956.475000000000000000"),
    )
    fee = D("0.09")
    x = D(100)
    y = D(100)

    balances = [x, y]
    f = 1 - fee

    # NOTE: The SOR tests (in the SOR repo) uses `tokenInIsToken0=true`, i.e., xin and yout.

    derived = eclp_prec_implementation.calc_derived_values(params)
    invariant, inv_err = eclp_prec_implementation.calculateInvariantWithError(
        balances, params, derived
    )
    r_vec = (invariant + 2 * inv_err, invariant)

    print("--- derived params ---")
    pprint(derived._asdict())

    print()
    print("--- should correctly calculate virtual offset 0 (a) ---")
    print(eclp_prec_implementation.virtualOffset0(params, derived, r_vec))

    print("--- should correctly calculate virtual offset 1 (b) ---")
    print(eclp_prec_implementation.virtualOffset1(params, derived, r_vec))

    print()
    print("--- should correctly calculate normalized liquidity ---")
    print(eclp_derivatives.normalized_liquidity_xin(balances, params, fee, r_vec))

    print("--- should correctly calculate swap amount for swap exact in ---")
    amount_in = D(10)
    amount_out = balances[1] - eclp_prec_implementation.calcYGivenX(
        balances[0] + f * amount_in, params, derived, r_vec
    )
    print(amount_out)

    print("--- should correctly calculate swap amount for swap exact out ---")
    amount_out = D(10)
    amount_in = (
        eclp_prec_implementation.calcXGivenY(
            balances[1] - amount_out, params, derived, r_vec
        )
        - balances[0]
    )
    amount_in /= f
    print(amount_in)

    print("--- should correctly calculate price after swap exact in ---")
    amount_in = D(10)
    py = 1 / eclp_derivatives.dyout_dxin(
        [balances[0] + f * amount_in, None], params, fee, r_vec
    )
    print(py)

    print("--- should correctly calculate price after swap exact out ---")
    amount_out = D(10)
    py = eclp_derivatives.dxin_dyout(
        [None, balances[1] - amount_out], params, fee, r_vec
    )
    print(py)

    print("--- should correctly calculate derivative of price after swap exact in ---")
    amount_in = D(10)
    dpy = eclp_derivatives.dpy_dxin(
        [balances[0] + f * amount_in, None], params, fee, r_vec
    )
    print(dpy)

    print("--- should correctly calculate derivative of price after swap exact out ---")
    amount_out = D(10)
    dpy = eclp_derivatives.dpy_dyout(
        [None, balances[1] - amount_out], params, fee, r_vec
    )
    print(dpy)

    print("--- BONUS: should not return negative numbers upon swap with 0 amount ---")
    # NB fees don't matter here.
    amount_in = D(0)
    amount_out = balances[1] - eclp_prec_implementation.calcYGivenX(
        balances[0] + f * amount_in, params, derived, r_vec
    )
    print(amount_out)


def calc_eclp_test_results_solidity():
    eclp_math_testing = accounts[0].deploy(GyroECLPMathTesting)

    """Calculate *some of* the test results via solidity, instead of the python prec impl."""
    params = ECLPMathParams(
        alpha=D("0.050000000000020290"),
        beta=D("0.397316269897841178"),
        c=D("0.9551573261744535"),
        s=D("0.29609877111408056"),
        l=D("748956.475000000000000000"),
    )
    fee = D("0.09")
    x = y = D(100)

    balances = [x, y]
    f = 1 - fee

    # NOTE: The SOR tests (in the SOR repo) uses `tokenInIsToken0=true`, i.e., xin and yout.

    derived = eclp_prec_implementation.calc_derived_values(params)
    invariant, inv_err = eclp_prec_implementation.calculateInvariantWithError(
        balances, params, derived
    )
    r_vec = (invariant + 2 * inv_err, invariant)

    print("--- BONUS: should not return negative numbers upon swap with 0 amount ---")
    # NB fees don't matter here.
    amount_in = D(0)

    # First variant: Via calcYGivenX
    amount_out = balances[1] - unscale(
        eclp_math_testing.calcYGivenX(
            scale(balances[0] + f * amount_in),
            scale(params),
            eclp_prec_implementation.scale_derived_values(derived),
            scale(r_vec),
        )
    )
    print(amount_out)

    # Second variant: Via calcOutGivenIn
    # The following is gonna revert. That's fine and expected behavior for such a low trade amount.
    try:
        amount_out = unscale(
            eclp_math_testing.calcOutGivenIn(
                scale(balances),
                scale(f * amount_in),
                True,
                scale(params),
                eclp_prec_implementation.scale_derived_values(derived),
                scale(r_vec),
            )
        )
        print(amount_out)
        print("Didn't revert! It should've though!")
    except VirtualMachineError as e:
        print(f"Reverted! {e}")


def calc_2clp_test_results():
    print("--- 2-CLP: should correctly calculate normalized liquidity, USDC > DAI ---")
    # Here we use x = out balance, y = in balance
    x = D(1232)
    y = D(1000)
    sqrtAlpha = D("0.9994998749")
    sqrtBeta = D("1.000499875")
    f = D(1) - D("0.009")

    l = unscale(
        gyro_two_math_testing.calculateInvariant(
            scale([x, y]), scale(sqrtAlpha), scale(sqrtBeta)
        )
    )

    # See the 2CLP/3CLP paper for why these are correct.
    # The blog post uses 1 / (dS / dyin) where S = yin/xout / p_x - 1.
    # Balancer instead uses 1/2 * 1 / (d/dyin yin/xout) for some reason.
    nliq_code = (x + l / sqrtBeta) / 2
    nliq_blog = (y + l * sqrtAlpha) / f
    print(f"OLD (blog post): {nliq_blog}")
    print(f"NEW (code):      {nliq_code}")

    print("--- 2-CLP: should correctly calculate normalized liquidity, DAI > USDC ---")
    # Now we need to use x = out balance and y = in balance.
    # NB We *cannot* just switch x and y; we'd also need to switch
    # sqrtBeta = D(1) / actual sqrtAlpha
    # sqrtAlpha = D(1) / actual sqrtBeta
    # That's because alpha and beta are denoted wrt. the y asset, i.e., there's a bias here.
    x = D(1232)
    y = D(1000)
    sqrtAlpha = D("0.9994998749")
    sqrtBeta = D("1.000499875")
    f = D(1) - D("0.009")

    l = unscale(
        gyro_two_math_testing.calculateInvariant(
            scale([x, y]), scale(sqrtAlpha), scale(sqrtBeta)
        )
    )

    nliq_code = (y + l * sqrtAlpha) / 2
    nliq_blog = (x + l / sqrtBeta) / f
    print(f"OLD (blog post):  {nliq_blog}")
    print(f"NEW (code):       {nliq_code}")

    print("--- 3-CLP: should correctly calculate normalized liquidity, USDT > USDC")
    # Again, x = out balance, y = in balance
    # Because of symmetry, we can choose arbitrarily which asset is which, unlike the 2-CLP.
    x = D(81485)
    y = D(83119)
    z = D(82934)
    root3Alpha = D("0.995647752")
    f = D(1) - D("0.003")
    l = unscale(
        gyro_three_math_testing.calculateInvariant(scale([x, y, z]), scale(root3Alpha))
    )

    nliq_code = (x + l * root3Alpha) / 2
    nliq_blog = (y + l * root3Alpha) / f
    print(f"OLD (blog post): {nliq_blog}")
    print(f"NEW (code):      {nliq_code}")


def calc_rate_scaled_eclp_test_results():
    params = ECLPMathParams(
        alpha=D("0.050000000000020290"),
        beta=D("0.397316269897841178"),
        c=D("0.9551573261744535"),
        s=D("0.29609877111408056"),
        l=D("748956.475000000000000000"),
    )
    fee = D("0.09")
    x, y = D("66.66666666666667"), D(
        100
    )  # x = 100/1.5 so that the rate-scaled balances are about equal
    ratex, ratey = D("1.5"), D("1")

    balances_nonscaled = [x, y]
    balances = [x * ratex, y * ratey]
    f = 1 - fee

    # NOTE: The SOR tests (in the SOR repo) uses `tokenInIsToken0=true`, i.e., xin and yout.

    derived = eclp_prec_implementation.calc_derived_values(params)
    invariant, inv_err = eclp_prec_implementation.calculateInvariantWithError(
        balances, params, derived
    )
    r_vec = (invariant + 2 * inv_err, invariant)

    print("--- derived params ---")
    pprint(derived._asdict())

    print()
    print("--- should correctly calculate virtual offset 0 (a, rate-scaled) ---")
    print(eclp_prec_implementation.virtualOffset0(params, derived, r_vec))

    print("--- should correctly calculate virtual offset 1 (b, rate-scaled) ---")
    print(eclp_prec_implementation.virtualOffset1(params, derived, r_vec))

    print()

    print("--- should correctly calculate limit amount for swap exact in")
    amount_in_max = (
        eclp_prec_implementation.maxBalances0(params, derived, r_vec) - balances[0]
    )
    print(amount_in_max / ratex / f * LIMIT_AMOUNT_IN_BUFFER_FACTOR)

    print("--- should correctly calculate limit amount for swap exact out")
    print(balances[1] / ratey)

    print("--- should correctly calculate normalized liquidity ---")
    print(
        D(1)
        / ratey
        * eclp_derivatives.normalized_liquidity_xin(balances, params, fee, r_vec)
    )

    print("--- should match universal normalized liquidity calculation ---")
    print(D(1) / (ratey * eclp_derivatives.dpy_dxin(balances, params, fee, r_vec)))

    print("--- should correctly calculate swap amount for swap exact in ---")
    amount_in = D(10) * ratex
    amount_out = balances[1] - eclp_prec_implementation.calcYGivenX(
        balances[0] + f * amount_in, params, derived, r_vec
    )
    print(amount_out / ratey)

    print(
        "--- should correctly calculate swap amount for swap exact out (ignore fee) ---"
    )
    amount_out = D(10) * ratey
    amount_in = (
        eclp_prec_implementation.calcXGivenY(
            balances[1] - amount_out, params, derived, r_vec
        )
        - balances[0]
    )
    print(amount_in / ratex)

    print("--- should correctly calculate price after swap exact in ---")
    amount_in = D(10) * ratex
    py = 1 / eclp_derivatives.dyout_dxin(
        [balances[0] + f * amount_in, None], params, fee, r_vec
    )
    print(py * ratey / ratex)

    print("--- should correctly calculate price after swap exact out ---")
    amount_out = D(10) * ratey
    py = eclp_derivatives.dxin_dyout(
        [None, balances[1] - amount_out], params, fee, r_vec
    )
    print(py * ratey / ratex)

    print("--- should correctly calculate derivative of price after swap exact in ---")
    amount_in = D(10) * ratex
    dpy = eclp_derivatives.dpy_dxin(
        [balances[0] + f * amount_in, None], params, fee, r_vec
    )
    print(dpy * ratey)

    print(
        "--- should correctly calculate derivative of price after swap exact in at 0 ---"
    )
    amount_in = D(0) * ratex
    dpy = eclp_derivatives.dpy_dxin(
        [balances[0] + f * amount_in, None], params, fee, r_vec
    )
    print(dpy * ratey)

    print("--- should correctly calculate derivative of price after swap exact out ---")
    amount_out = D(10)
    dpy = eclp_derivatives.dpy_dyout(
        [None, balances[1] - amount_out], params, fee, r_vec
    )
    print(dpy * ratey**2 / ratex)

    print("--- BONUS: should not return negative numbers upon swap with 0 amount ---")
    # NB fees don't matter here.
    amount_in = D(0) * ratex
    amount_out = balances[1] - eclp_prec_implementation.calcYGivenX(
        balances[0] + f * amount_in, params, derived, r_vec
    )
    print(amount_out / ratey)


def main():
    calc_2clp_test_results()
    calc_eclp_test_results()
