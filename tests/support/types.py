from typing import NamedTuple, Tuple, Iterable

from tests.support.quantized_decimal import DecimalLike

address = str


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
    oracleEnabled: bool
    owner: str


class CapParams(NamedTuple):
    cap_enabled: bool = False
    per_address_cap: int = 0
    global_cap: int = 0


class TwoPoolFactoryCreateParams(NamedTuple):
    name: str
    symbol: str
    tokens: list[str]
    sqrts: list[DecimalLike]
    swapFeePercentage: DecimalLike
    oracleEnabled: bool
    owner: address
    cap_params: CapParams = CapParams()


class TwoPoolParams(NamedTuple):
    baseParams: TwoPoolBaseParams
    sqrtAlpha: DecimalLike  # should already be upscaled
    sqrtBeta: DecimalLike  # Should already be upscaled
    cap_params: CapParams = CapParams()


class ThreePoolParams(NamedTuple):
    vault: str
    name: str
    symbol: str
    tokens: list[str]
    root3Alpha: DecimalLike
    swapFeePercentage: DecimalLike
    pauseWindowDuration: DecimalLike
    bufferPeriodDuration: DecimalLike
    owner: str
    # configAddress listed separately


class Vector2(NamedTuple):
    x: DecimalLike
    y: DecimalLike


class CEMMMathParams(NamedTuple):
    alpha: DecimalLike
    beta: DecimalLike
    c: DecimalLike
    s: DecimalLike
    l: DecimalLike


class CEMMMathQParams(NamedTuple):
    a: DecimalLike
    b: DecimalLike
    c: DecimalLike


class CEMMMathDerivedParams(NamedTuple):
    tauAlpha: Vector2
    tauBeta: Vector2
    u: DecimalLike
    v: DecimalLike
    w: DecimalLike
    z: DecimalLike
    dSq: DecimalLike


class ThreePoolFactoryCreateParams(NamedTuple):
    name: str
    symbol: str
    tokens: list[str]
    root3Alpha: DecimalLike
    swapFeePercentage: DecimalLike
    owner: address


# Legacy Aliases
GyroCEMMMathParams = CEMMMathParams
GyroCEMMMathDerivedParams = CEMMMathDerivedParams


class CEMMPoolParams(NamedTuple):
    baseParams: TwoPoolBaseParams
    cemmParams: GyroCEMMMathParams
    derivedCEMMParams: GyroCEMMMathDerivedParams
