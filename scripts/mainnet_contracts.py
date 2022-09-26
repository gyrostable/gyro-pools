from functools import lru_cache
from brownie import (
    ETH_ADDRESS,
    ZERO_ADDRESS,
    accounts,
    SimpleERC20,
    SimpleERC20CustomDecimal,
)
from brownie.network import chain

from scripts.constants import STABLE_COINS, TOKEN_ADDRESSES


@lru_cache()
def get_token_address(name, is_fork=True) -> str:
    chain_id = chain.id
    if chain_id == 1337:
        if is_fork:
            chain_id = 1
        else:
            if name in ("USDC", "USDT"):
                token = accounts[0].deploy(SimpleERC20CustomDecimal, 6)
                token.mint(accounts[0], 10**12)
            else:
                token = accounts[0].deploy(SimpleERC20)
                token.mint(accounts[0], 10**24)
            return token.address
    if chain_id not in TOKEN_ADDRESSES:
        raise ValueError(f"chain {chain_id} not supported")
    return TOKEN_ADDRESSES[chain_id].get(name, ZERO_ADDRESS)


class TokenAddresses:
    ETH = ETH_ADDRESS

    @classmethod
    @property
    def DAI(cls):
        return get_token_address("DAI")

    @classmethod
    @property
    def WBTC(cls):
        return get_token_address("WBTC")

    @classmethod
    @property
    def USDC(cls):
        return get_token_address("USDC")

    @classmethod
    @property
    def WETH(cls):
        return get_token_address("WETH")

    @classmethod
    @property
    def CRV(cls):
        return get_token_address("CRV")

    @classmethod
    @property
    def TUSD(cls):
        return get_token_address("TUSD")

    @classmethod
    @property
    def USDP(cls):
        return get_token_address("USDP")

    @classmethod
    @property
    def PAXG(cls):
        return get_token_address("PAXG")

    @classmethod
    @property
    def AAVE(cls):
        return get_token_address("AAVE")

    @classmethod
    @property
    def LUSD(cls):
        return get_token_address("LUSD")

    @classmethod
    @property
    def COMP(cls):
        return get_token_address("COMP")

    @classmethod
    @property
    def USDT(cls):
        return get_token_address("USDT")

    @classmethod
    @property
    def GUSD(cls):
        return get_token_address("GUSD")

    @classmethod
    @property
    def HUSD(cls):
        return get_token_address("HUSD")


_chainlink_feeds = {
    1: {
        "ETH_USD_FEED": "0x5f4eC3Df9cbd43714FE2740f5E3616155c5b8419",
        "DAI_USD_FEED": "0xAed0c38402a5d19df6E4c03F4E2DceD6e29c1ee9",
        "WBTC_USD_FEED": "0xF4030086522a5bEEa4988F8cA5B36dbC97BeE88c",
        "CRV_USD_FEED": "0xCd627aA160A6fA45Eb793D19Ef54f5062F20f33f",
        "USDC_USD_FEED": "0x8fFfFfd4AfB6115b954Bd326cbe7B4BA576818f6",
        "USDT_USD_FEED": "0x3E7d1eAB13ad0104d2750B8863b489D65364e32D",
    },
    137: {
        "ETH_USD_FEED": "0xF9680D99D6C9589e2a93a78A04A279e509205945",
        "DAI_USD_FEED": "0x4746DeC9e833A82EC7C2C1356372CcF2cfcD2F3D",
        "WBTC_USD_FEED": "0xDE31F8bFBD8c84b5360CFACCa3539B938dd78ae6",
        "USDC_USD_FEED": "0xfE4A8cc5b5B2366C1B58Bea3858e81843581b2F7",
        "USDT_USD_FEED": "0x0A6513e40db6EB1b165753AD52E80663aeA50545",
    },
}


def _chainlink_feed(name) -> str:
    chain_id = chain.id
    if chain_id == 1337:
        chain_id = 1
    if chain_id not in _chainlink_feeds:
        raise ValueError(f"chain {chain_id} not supported")
    return _chainlink_feeds[chain_id].get(name, ZERO_ADDRESS)


class ChainlinkFeeds:
    @classmethod
    @property
    def ETH_USD_FEED(cls):
        return _chainlink_feed("ETH_USD_FEED")

    @classmethod
    @property
    def DAI_USD_FEED(cls):
        return _chainlink_feed("DAI_USD_FEED")

    @classmethod
    @property
    def WBTC_USD_FEED(cls):
        return _chainlink_feed("WBTC_USD_FEED")

    @classmethod
    @property
    def CRV_USD_FEED(cls):
        return _chainlink_feed("CRV_USD_FEED")

    @classmethod
    @property
    def USDC_USD_FEED(cls):
        return _chainlink_feed("USDC_USD_FEED")

    @classmethod
    @property
    def USDT_USD_FEED(cls):
        return _chainlink_feed("USDT_USD_FEED")


_uniswap_pools = {
    1: {
        "USDC_ETH": "0x8ad599c3a0ff1de082011efddc58f1908eb6e6d8",
        "ETH_CRV": "0x4c83A7f819A5c37D64B4c5A2f8238Ea082fA1f4e",
        "WBTC_USDC": "0x99ac8cA7087fA4A2A1FB6357269965A2014ABc35",
        "DAI_ETH": "0x60594a405d53811d3BC4766596EFD80fd545A270",
        "USDT_ETH": "0x4e68ccd3e89f51c3074ca5072bbac773960dfa36",
    },
    137: {
        "USDC_ETH": "0x45dDa9cb7c25131DF268515131f647d726f50608",
        "WBTC_USDC": "0x847b64f9d3A95e977D157866447a5C0A5dFa0Ee5",
        "USDT_ETH": "0x4CcD010148379ea531D6C587CfDd60180196F9b1",
    },
}


def _get_uniswap_pool(name) -> str:
    chain_id = chain.id
    if chain_id == 1337:
        chain_id = 1
    if chain_id not in _uniswap_pools:
        raise ValueError(f"chain {chain_id} not supported")
    return _uniswap_pools[chain_id].get(name, ZERO_ADDRESS)


class UniswapPools:
    @classmethod
    @property
    def USDC_ETH(cls):
        return _get_uniswap_pool("USDC_ETH")

    @classmethod
    @property
    def ETH_CRV(cls):
        return _get_uniswap_pool("ETH_CRV")

    @classmethod
    @property
    def WBTC_USDC(cls):
        return _get_uniswap_pool("WBTC_USDC")

    @classmethod
    @property
    def DAI_ETH(cls):
        return _get_uniswap_pool("DAI_ETH")

    @classmethod
    @property
    def USDT_ETH(cls):
        return _get_uniswap_pool("USDT_ETH")

    @classmethod
    def all_pools(cls):
        return [
            pool
            for v in dir(cls)
            if not v.startswith("_")
            and v != "all_pools"
            and (pool := getattr(UniswapPools, v)) != ZERO_ADDRESS
        ]


def get_chainlink_feeds():
    if chain.id in (1, 1337):
        return [
            (TokenAddresses.ETH, ChainlinkFeeds.ETH_USD_FEED),
            (TokenAddresses.WETH, ChainlinkFeeds.ETH_USD_FEED),
            (TokenAddresses.DAI, ChainlinkFeeds.DAI_USD_FEED),
            (TokenAddresses.WBTC, ChainlinkFeeds.WBTC_USD_FEED),
            (TokenAddresses.CRV, ChainlinkFeeds.CRV_USD_FEED),
            (TokenAddresses.USDC, ChainlinkFeeds.USDC_USD_FEED),
            (TokenAddresses.USDT, ChainlinkFeeds.USDT_USD_FEED),
        ]
    if chain.id == 137:
        return [
            (TokenAddresses.ETH, ChainlinkFeeds.ETH_USD_FEED),
            (TokenAddresses.WETH, ChainlinkFeeds.ETH_USD_FEED),
            (TokenAddresses.DAI, ChainlinkFeeds.DAI_USD_FEED),
            (TokenAddresses.WBTC, ChainlinkFeeds.WBTC_USD_FEED),
            (TokenAddresses.USDC, ChainlinkFeeds.USDC_USD_FEED),
            (TokenAddresses.USDT, ChainlinkFeeds.USDT_USD_FEED),
        ]
    raise ValueError(f"chain {chain.id} not supported")


def is_stable(asset):
    return asset in [getattr(TokenAddresses, v) for v in STABLE_COINS]
