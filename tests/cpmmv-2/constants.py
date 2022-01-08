from collections import namedtuple

JOIN_POOL_REQUEST = namedtuple(
    "JoinPoolRequest",
    [
        "assets",  # IAsset[] => address[]
        "maxAmountsIn",  # uint256[]
        "userData",  # bytes
        "fromInternalBalance",  # bool
    ],
)

SWAP_REQUEST = namedtuple(
    "SwapRequest",
    [
        "kind",  # SwapKind
        "tokenIn",  # IERC20
        "tokenOut",  # IERC20
        "amount",  # uint256
        "poolId",  # bytes32
        "lastChangeBlock",  # uint256
        "from_aux",  # address
        "to",  # address
        "userData",  # bytes
    ],
)

TO_LIST = namedtuple(
    "ToList",
    [
        "element0",  #
        "element1",
    ],
)


NUM_TOKENS = 2
NUM_USERS = 2
ADDRESS_0 = "0x0000000000000000000000000000000000000000"
