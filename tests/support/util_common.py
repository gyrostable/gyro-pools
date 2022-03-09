from contextlib import contextmanager
from dataclasses import dataclass
from unicodedata import decimal

from hypothesis import strategies as st, assume

from tests.support.types import Vector2
from tests.support.utils import qdecimals
from tests.support.quantized_decimal import QuantizedDecimal as D


@dataclass
class BasicPoolParameters:
    min_price_separation: D
    max_in_ratio: D
    max_out_ratio: D
    min_balance_ratio: D
    min_fee: D


billion_balance_strategy = st.integers(min_value=0, max_value=100_000_000_000)


@st.composite
def gen_balances(draw, n: int, bparams: BasicPoolParameters):
    balances = [draw(billion_balance_strategy) for _ in range(n)]

    for i in range(n):
        for j in range(n):
            assume(balances[j] > 0)
            assume(balances[i] / balances[j] > bparams.min_balance_ratio)

    return balances


def gen_balances_vector(bparams: BasicPoolParameters):
    return gen_balances(2, bparams).map(lambda args: Vector2(*args))


@contextmanager
def debug_postmortem_on_exc(use_pdb=True):
    """When use_pdb is True, enter the debugger if an exception is raised."""
    try:
        yield
    except Exception as e:
        if not use_pdb:
            raise
        import sys
        import traceback
        import pdb

        info = sys.exc_info()
        traceback.print_exception(*info)
        pdb.post_mortem(info[2])
