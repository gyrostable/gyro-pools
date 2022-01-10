from typing import NamedTuple

address = str


class SwapKind:
    GivenIn = 0
    GivenOut = 1


class CallJoinPoolGyroParams(NamedTuple):
    gyroTwoPool: address
    poolId: bytes
    sender: address
    recipient: address
    currentBalances: int
    lastChangeBlock: int
    protocolSwapFeePercentage: int
    amountIn: int
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
