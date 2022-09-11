from brownie import *

from tests.support.quantized_decimal import QuantizedDecimal as D
from tests.support.utils import scale, unscale

gyro_two_math_testing = accounts[0].deploy(Gyro2CLPMathTesting)
gyro_three_math_testing = accounts[0].deploy(Gyro3CLPMathTesting)


def main():
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
