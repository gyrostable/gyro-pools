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

    l = unscale(gyro_two_math_testing.calculateInvariant(scale([x, y]), scale(sqrtAlpha), scale(sqrtBeta)))

    # See the 2CLP/3CLP paper for why these are correct.
    nliq_xout = x + l / sqrtBeta
    nliq_yin = (y + l * sqrtAlpha) / f
    print(f"OLD (wrt yin):  {nliq_yin}")
    print(f"NEW (wrt xout): {nliq_xout}")

    print("--- 2-CLP: should correctly calculate normalized liquidity, DAI > USDC ---")
    y = D(1232)
    x = D(1000)
    sqrtAlpha = D("0.9994998749")
    sqrtBeta = D("1.000499875")
    f = D(1) - D("0.009")

    l = unscale(gyro_two_math_testing.calculateInvariant(scale([x, y]), scale(sqrtAlpha), scale(sqrtBeta)))

    nliq_xout = x + l / sqrtBeta
    nliq_yin = (y + l * sqrtAlpha) / f
    print(f"OLD (wrt yin):  {nliq_yin}")
    print(f"NEW (wrt xout): {nliq_xout}")

    print("--- 3-CLP: should correctly calculate normalized liquidity, USDT > USDC")
    # Again, x = out balance, y = in balance
    x = D(81485)
    y = D(83119)
    z = D(82934)
    root3Alpha = D("0.995647752")
    f = D(1) - D("0.003")
    l = unscale(gyro_three_math_testing.calculateInvariant(scale([x, y, z]), scale(root3Alpha)))

    nliq_xout = x + l * root3Alpha
    nliq_yin = (y + l * root3Alpha) / f
    print(f"OLD (wrt yin):  {nliq_yin}")
    print(f"NEW (wrt xout): {nliq_xout}")
