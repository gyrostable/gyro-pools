import decimal
import operator

import hypothesis.strategies as st
from hypothesis import example, settings, assume
from brownie.test import given

from tests.support.quantized_decimal import QuantizedDecimal as D
from tests.support.utils import scale, qdecimals, unscale
from math import floor, log2, log10, ceil

operators = ["add", "sub", "mul", "truediv"]

MAX_UINT = 2**256 - 1


@given(
    a=st.decimals(min_value=0, allow_nan=False, allow_infinity=False),
    b=st.decimals(min_value=0, allow_nan=False, allow_infinity=False),
    ops=st.lists(st.sampled_from(operators), min_size=1),
)
def test_decimal_behavior(math_testing, a, b, ops):
    a, b = D(a), D(b)
    for op_name in ops:
        op = getattr(operator, op_name)
        if b > a and op_name == "sub":
            b = a
        if b == 0 and op_name == "truediv":
            b = D(1)
        try:
            if (
                (op_name == "mul" and a * b > unscale(MAX_UINT, 36))
                or (op_name == "add" and a + b > unscale(MAX_UINT, 18))
                or (op_name == "div" and a > unscale(MAX_UINT, 18))
            ):
                a = D(1)
        # failed to quantize because op(a, b) is too large
        except decimal.InvalidOperation:
            a = D(1)
        solidity_b = getattr(math_testing, op_name)(scale(a), scale(b))
        a, b = b, op(a, b)
        assert scale(b) == solidity_b


@st.composite
def gen_samples_sqrt(draw):
    # We generate samples that are "logarithmically uniform", to get more diverse orders of magnitude than would
    # ordinarily be generated.
    # Since the Newton method divides the input by something, the max we can do is 1.15e41. We go to 9e40.
    mantissa = draw(qdecimals(1, 9))
    exponent = draw(qdecimals(-18, 40))
    return mantissa * D(10) ** exponent


@settings(max_examples=1_000)
@given(a=gen_samples_sqrt())
@example(a=D(1))
@example(a=D(0))
@example(a=D("1E-18"))
def test_sqrt(math_testing, a):
    # Note that errors are relatively large, with, e.g., 5 decimals for sqrt(1)
    res_math = a.sqrt()
    res_sol = math_testing.sqrt(scale(a))
    # Absolute error tolerated in the last decimal + the default relative error.
    # Note this is pretty tight: sqrt(1.0) has relative error 1.001e-14. Could use a higher abs error
    assert int(res_sol) == scale(res_math).approxed(abs=D("5"), rel=D("1.5e-14"))


@settings(max_examples=1_000)
@given(a=gen_samples_sqrt())
@example(a=D(1))
@example(a=D("1E-18"))
def test_sqrtNewton(math_testing, a):
    res_math = a.sqrt()
    res_sol = math_testing.sqrtNewton(scale(a), 5)

    assert int(res_sol) == scale(res_math).approxed(abs=D("5"))


@given(a=qdecimals(0).filter(lambda a: a > 0))
@example(a=D(1))
@example(a=D("1E-17"))
@example(a=D("1E-18"))
def test_sqrtNewtonInitialGuess(math_testing, a):
    result_sol = unscale(math_testing.sqrtNewtonInitialGuess(scale(a)))
    if a >= 1:
        assert result_sol == 2 ** (floor(log2(a) / 2))
    elif a == D("1E-18"):
        # Special case where it's not worth introducing another case in the solidity code.
        # The rule below would yield 1E-9, i.e., the exact result, but our code includes this
        # in the next higher case.
        assert result_sol == D("1E-17").sqrt()
    elif a <= 0.1:
        a_oom = D(10) ** ceil(log10(a))
        assert result_sol == a_oom.sqrt()
    else:  # a in (0.1, 1)
        assert result_sol == a
