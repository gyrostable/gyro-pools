from math import pi, sin, cos

from hypothesis import strategies as st

from tests.cemm import cemm as mimpl
from tests.support.quantized_decimal import QuantizedDecimal as D
from tests.support.types import CEMMMathParams, CEMMMathDerivedParams, Vector2
from tests.support.utils import qdecimals

billion_balance_strategy = st.integers(min_value=0, max_value=1_000_000_000)


def params2MathParams(params: CEMMMathParams) -> mimpl.Params:
    """The python math implementation is a bit older and uses its own data structures. This function converts."""
    return mimpl.Params(params.alpha, params.beta, params.c, -params.s, params.l)


def mathParams2DerivedParams(mparams: mimpl.Params) -> CEMMMathDerivedParams:
    return CEMMMathDerivedParams(
        tauAlpha=Vector2(*mparams.tau_alpha),
        tauBeta=Vector2(*mparams.tau_beta)
    )


@st.composite
def gen_params(draw):
    phi_degrees = draw(st.floats(10, 80))
    phi = phi_degrees / 360 * 2 * pi
    s = sin(phi)
    c = cos(phi)
    l = draw(qdecimals("1", "10"))
    alpha = draw(qdecimals("0.05", "0.995"))
    beta = draw(qdecimals("1.005", "20.0"))
    return CEMMMathParams(alpha, beta, D(c), D(s), l)


def gen_balances():
    return st.tuples(billion_balance_strategy, billion_balance_strategy)


def gen_balances_vector():
    return gen_balances().map(lambda args: Vector2(*args))