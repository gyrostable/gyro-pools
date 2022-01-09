from logging import warning
from typing import Iterable

from tests.support.quantized_decimal import QuantizedDecimal as D

_MAX_IN_RATIO = D("0.3")
_MAX_OUT_RATIO = D("0.3")

# Kinda arbitrary. It also almost doesn't matter b/c Newton is so fast in the end.
prec_convergence = D("1E-18")
# TODO I guess this should match precision of QuantizedDecimal.


def calculateInvariant(balances: Iterable[D], sqrtAlpha: D, sqrtBeta: D) -> D:
    (a, mb, mc) = calculateQuadraticTerms(balances, sqrtAlpha, sqrtBeta)
    return calculateQuadraticSpecial(a, mb, mc)


def calculateQuadraticTerms(
    balances: Iterable[D], sqrtAlpha: D, sqrtBeta: D
) -> tuple[D, D, D]:
    x, y = balances
    a = 1 - sqrtAlpha / sqrtBeta
    b = -(y / sqrtBeta + x * sqrtAlpha)
    c = -x * y
    return a, -b, -c


# This function is not a complete match to _calculateQuadratic in GyroTwoMath.sol, this is just general quadratic formula


def calculateQuadratic(a: D, b: D, c: D) -> D:
    assert b * b - 4 * a * c >= 0
    numerator = -b + (b * b - 4 * a * c).sqrt()
    denominator = a * 2
    return numerator / denominator


# This function should match _calculateQuadratic in GyroTwoMath.sol in both inputs and outputs
# when a > 0, b < 0, and c < 0


def calculateQuadraticSpecial(a: D, mb: D, mc: D) -> D:
    assert a > 0 and mb > 0 and mc >= 0
    return calculateQuadratic(a, -mb, -mc)


def liquidityInvariantUpdate(
    balances: Iterable[D],
    sqrtAlpha: D,
    sqrtBeta: D,
    lastInvariant: D,
    diffY: D,
    isIncreaseLiq: bool,
) -> D:
    x, y = balances
    virtualX = x + lastInvariant / sqrtBeta
    sqrtPx = calculateSqrtPrice(lastInvariant, virtualX)
    diffInvariant = diffY / (sqrtPx - sqrtAlpha)
    if isIncreaseLiq == True:
        invariant = lastInvariant + diffInvariant
    else:
        invariant = lastInvariant - diffInvariant
    return invariant


def calcOutGivenIn(
    balanceIn: D,
    balanceOut: D,
    amountIn: D,
    virtualParamIn: D,
    virtualParamOut: D,
    currentInvariant: D,
) -> D:
    assert amountIn <= balanceIn * _MAX_IN_RATIO
    virtIn = balanceIn + virtualParamIn
    virtOut = balanceOut + virtualParamOut
    return virtOut - currentInvariant * currentInvariant / (virtIn + amountIn)


def calcInGivenOut(
    balanceIn: D,
    balanceOut: D,
    amountOut: D,
    virtualParamIn: D,
    virtualParamOut: D,
    currentInvariant: D,
) -> D:
    assert amountOut <= balanceOut * _MAX_OUT_RATIO
    virtOut = balanceOut + virtualParamOut
    virtIn = balanceIn + virtualParamIn
    return currentInvariant * currentInvariant / (virtOut - amountOut) - virtIn


def calcAllTokensInGivenExactBptOut(
    balances: Iterable[D], bptAmountOut: D, totalBPT: D
) -> tuple[D, D]:
    bptRatio = bptAmountOut / totalBPT
    x, y = balances
    return x * bptRatio, y * bptRatio


def calcTokensOutGivenExactBptIn(
    balances: Iterable[D], bptAmountIn: D, totalBPT: D
) -> tuple[D, D]:
    bptRatio = bptAmountIn / totalBPT
    x, y = balances
    return x * bptRatio, y * bptRatio


def calcDueTokenProtocolSwapFeeAmount(
    balances: Iterable[D],
    previousInvariant: D,
    currentInvariant: D,
    protocolSwapFeePercentage: D,
    sqrtParams: Iterable[D],
) -> tuple[D, D]:
    if currentInvariant <= previousInvariant:
        return 0, 0

    deltaL = protocolSwapFeePercentage * (currentInvariant - previousInvariant)
    sqrtAlpha, sqrtBeta = sqrtParams
    x, y = balances
    a = calculateVirtualParameter0(currentInvariant, sqrtBeta)
    sqrtPrice = calculateSqrtPrice(currentInvariant, x + a)

    dueProtocolFeeAmountX = deltaL * (1 / sqrtPrice - 1 / sqrtBeta)
    dueProtocolFeeAmountY = deltaL * (sqrtPrice - sqrtAlpha)
    return dueProtocolFeeAmountX, dueProtocolFeeAmountY


def calculateVirtualParameter0(invariant: D, sqrtBeta: D) -> D:
    return invariant / sqrtBeta


def calculateVirtualParameter1(invariant: D, sqrtAlpha: D) -> D:
    return invariant * sqrtAlpha


def calculateSqrtPrice(invariant: D, virtualX: D) -> D:
    return invariant / virtualX
