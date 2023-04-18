from __future__ import annotations
import sys
from typing import Generic, NamedTuple, Tuple, Iterable, TypeVar

from brownie import ZERO_ADDRESS

from tests.support.quantized_decimal import DecimalLike, QuantizedDecimal as QD
from tests.support.quantized_decimal_38 import QuantizedDecimal as QD38


# NOTE: Python 3.9 and 3.10 disallow multiple inheritance for NamedTuple
# This behavior is "fixed" in 3.11, so we just need this nasty monkey patching
# for these two versions
if sys.version_info.minor in (9, 10):
    from typing import _NamedTuple  # type: ignore

    def _namedtuple_mro_entries(bases):
        assert bases[0] is NamedTuple
        return (_NamedTuple,)

    NamedTuple.__mro_entries__ = _namedtuple_mro_entries  # type: ignore


address = str

DEFAULT_CAP_MANAGER = "0x66aB6D9362d4F35596279692F0251Db635165871"
DEFAULT_PAUSE_MANAGER = "0x66aB6D9362d4F35596279692F0251Db635165871"


class SwapKind:
    GivenIn = 0
    GivenOut = 1


class CallJoinPoolGyroParams(NamedTuple):
    pool: address
    poolId: bytes
    sender: address
    recipient: address
    currentBalances: Tuple[int, ...]
    lastChangeBlock: int
    protocolSwapFeePercentage: int
    amountIn: Iterable[int]
    bptOut: int


class SwapRequest(NamedTuple):
    kind: int
    tokenIn: address
    tokenOut: address
    amount: int
    poolId: bytes
    lastChangeBlock: int
    from_aux: address
    to: address
    userData: bytes


class TwoPoolBaseParams(NamedTuple):
    vault: str
    name: str
    symbol: str
    token0: str
    token1: str
    swapFeePercentage: DecimalLike
    pauseWindowDuration: DecimalLike
    bufferPeriodDuration: DecimalLike
    owner: str


class CapParams(NamedTuple):
    cap_enabled: bool = False
    per_address_cap: DecimalLike = 0
    global_cap: DecimalLike = 0


class TwoPoolFactoryCreateParams(NamedTuple):
    name: str
    symbol: str
    tokens: list[str]
    sqrts: list[int]
    swapFeePercentage: DecimalLike
    owner: address
    cap_manager: address = DEFAULT_CAP_MANAGER
    cap_params: CapParams = CapParams()
    pause_manager: address = DEFAULT_PAUSE_MANAGER


class TwoPoolParams(NamedTuple):
    baseParams: TwoPoolBaseParams
    sqrtAlpha: DecimalLike  # should already be upscaled
    sqrtBeta: DecimalLike  # Should already be upscaled
    cap_manager: address = DEFAULT_CAP_MANAGER
    cap_params: CapParams = CapParams()
    pauseManager: address = DEFAULT_PAUSE_MANAGER


T = TypeVar("T")


class Vector2Base(NamedTuple, Generic[T]):
    x: T
    y: T

    # For compatibility with tuple representation
    def __getitem__(self, ix) -> T:
        if ix not in (0, 1):
            raise KeyError(f"Only indices 0, 1 supported. Given: {ix}")
        return (self.x, self.y)[ix]


class Vector2(Vector2Base[DecimalLike]):
    pass


class ECLPMathParamsBase(NamedTuple, Generic[T]):
    alpha: T
    beta: T
    c: T
    s: T
    l: T


class ECLPMathParams(ECLPMathParamsBase[DecimalLike]):
    pass


class ECLPMathParamsQD(ECLPMathParamsBase[QD]):
    def scale(self) -> ECLPMathParamsQD:
        multiplier = 10**18
        params = type(self)(
            alpha=self.alpha * multiplier,
            beta=self.beta * multiplier,
            c=self.c * multiplier,
            s=self.s * multiplier,
            l=self.l * multiplier,
        )
        return params


class ECLPMathQParams(NamedTuple):
    a: DecimalLike
    b: DecimalLike
    c: DecimalLike


class ECLPMathDerivedParamsBase(NamedTuple, Generic[T]):
    tauAlpha: Vector2Base[T]
    tauBeta: Vector2Base[T]
    u: T
    v: T
    w: T
    z: T
    dSq: T


class ECLPMathDerivedParams(ECLPMathDerivedParamsBase[DecimalLike]):
    pass


class ECLPMathDerivedParamsQD38(ECLPMathDerivedParamsBase[QD38]):
    def scale(self) -> ECLPMathDerivedParamsQD38:
        multiplier = 10**38
        derived = type(self)(
            tauAlpha=Vector2Base[QD38](
                self.tauAlpha[0] * multiplier, self.tauAlpha[1] * multiplier
            ),
            tauBeta=Vector2Base[QD38](
                self.tauBeta[0] * multiplier, self.tauBeta[1] * multiplier
            ),
            u=self.u * multiplier,
            v=self.v * multiplier,
            w=self.w * multiplier,
            z=self.z * multiplier,
            dSq=self.dSq * multiplier,
            # dAlpha=d.dAlpha * D2("1e38"),
            # dBeta=d.dBeta * D2("1e38"),
        )
        return derived


class ThreePoolFactoryCreateParams(NamedTuple):
    name: str
    symbol: str
    tokens: list[str]
    swapFeePercentage: DecimalLike
    root3Alpha: DecimalLike
    owner: address
    cap_manager: address = DEFAULT_CAP_MANAGER
    cap_params: CapParams = CapParams()
    pause_manager: address = DEFAULT_PAUSE_MANAGER


class ThreePoolParams(NamedTuple):
    vault: str
    config_address: address
    config: ThreePoolFactoryCreateParams
    pauseWindowDuration: int
    bufferPeriodDuration: int


# Legacy Aliases
GyroECLPMathParams = ECLPMathParams
GyroECLPMathDerivedParams = ECLPMathDerivedParams


class ECLPPoolParams(NamedTuple):
    baseParams: TwoPoolBaseParams
    eclpParams: ECLPMathParamsQD
    derivedECLPParams: ECLPMathDerivedParamsQD38
    rateProvider0: address = ZERO_ADDRESS
    rateProvider1: address = ZERO_ADDRESS
    cap_manager: address = DEFAULT_CAP_MANAGER
    cap_params: CapParams = CapParams()
    pauseManager: address = DEFAULT_PAUSE_MANAGER


class ECLPFactoryCreateParams(NamedTuple):
    name: str
    symbol: str
    tokens: list[str]
    params: ECLPMathParamsQD
    derived_params: ECLPMathDerivedParamsQD38
    rate_providers: list[str]  # Default [ZERO_ADDRESS, ZERO_ADDRESS]
    swap_fee_percentage: DecimalLike
    owner: str
    cap_manager: address = DEFAULT_CAP_MANAGER
    cap_params: CapParams = CapParams()
    pause_manager: address = DEFAULT_PAUSE_MANAGER
