from decimal import Decimal
from typing import Tuple

import hypothesis.strategies as st
import pytest
from brownie.test import given
from tests.support.utils import scale, to_decimal, qdecimals

from operator import add

billion_balance_strategy = st.integers(min_value=0, max_value=1_000_000_000)

def triple_uniform_integers(min_value=0, max_value=1_000_000_000):
    g = st.integers(min_value=min_value, max_value=max_value)
    return st.tuples(g, g, g)

def gen_balances():
    return st.tuples(billion_balance_strategy, billion_balance_strategy, billion_balance_strategy)

def gen_root3Alpha():
    return qdecimals(min_value="0.9", max_value="0.99996")

@given(
    balances=gen_balances(),
    root3Alpha=gen_root3Alpha(),
    addl_balances=triple_uniform_integers(500_000_000)
)
def test_calculateInvariant_growth(gyro_three_math_testing, balances, root3Alpha, addl_balances):
    l_low = gyro_three_math_testing.calculateInvariant(
        scale(balances), scale(root3Alpha)
    )

    balances_high = tuple(map(add, balances, addl_balances))
    l_high = gyro_three_math_testing.calculateInvariant(
        scale(balances_high), scale(root3Alpha)
    )

    assert l_low < l_high

