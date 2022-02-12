from math import pi, sin, cos, tan

from hypothesis import strategies as st, assume

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

    # Price bounds. Choose s.t. the 'peg' lies approximately within the bounds (within 30%).
    # It'd be nonsensical if this was not the case: Why are we using an ellipse then?!
    peg = tan(phi)  # = price where the flattest point of the ellipse lies.
    peg = D(peg)
    alpha_high = peg * D('1.3')
    beta_low = peg * D('0.7')
    alpha = draw(qdecimals("0.05", alpha_high.raw))
    beta  = draw(qdecimals(beta_low, "20.0"))

    s = sin(phi)
    c = cos(phi)
    l = draw(qdecimals("1", "10"))
    return CEMMMathParams(alpha, beta, D(c), D(s), l)


def gen_balances():
    return st.tuples(billion_balance_strategy, billion_balance_strategy)


def gen_balances_vector():
    return gen_balances().map(lambda args: Vector2(*args))


@st.composite
def gen_params_cemm_dinvariant(draw):
    params = draw(gen_params())
    mparams = params2MathParams(params)
    balances = draw(gen_balances())
    cemm = mimpl.CEMM.from_x_y(balances[0], balances[1], mparams)
    dinvariant = draw(
        qdecimals(-cemm.r.raw, 2 * cemm.r.raw)
    )  # Upper bound kinda arbitrary
    assume(abs(dinvariant) > D("1E-10"))  # Only relevant updates
    return params, cemm, dinvariant