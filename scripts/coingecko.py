from typing import Dict, List, Callable, TypeVar

import requests

T = TypeVar("T")

LEGACY_MAPPINGS = {
    "0x9c9e5fd8bbc25984b178fdce6117defa39d2db39": "0xdab529f40e671a1d4bf91361c21bf9f0c9712ab7",
}


def get_asset_platforms():
    r = requests.get("https://api.coingecko.com/api/v3/asset_platforms")
    r.raise_for_status()
    return r.json()


def get_coins() -> List[dict]:
    r = requests.get(
        "https://api.coingecko.com/api/v3/coins/list?include_platform=true"
    )
    r.raise_for_status()
    return r.json()


def find(
    haystack: List[T],
    predicate: Callable[[T], bool],
    error_msg: str = "could not find item in list",
) -> T:
    for item in haystack:
        if predicate(item):
            return item
    raise ValueError(error_msg)


def get_asset_platform_id(chain_id: int) -> str:
    asset_platforms = get_asset_platforms()
    return find(asset_platforms, lambda x: x["chain_identifier"] == chain_id)["id"]


def get_coin_ids(addresses: List[str], platform_id: str) -> List[str]:
    coins = get_coins()
    coin_ids = []
    for address in addresses:
        coin = find(
            coins,
            lambda x: x["platforms"].get(platform_id, "").lower() == address.lower(),
        )
        coin_ids.append(coin["id"])
    return coin_ids


def get_prices(addresses: List[str], chain_id: int = 1) -> Dict[str, float]:
    asset_platform_id = get_asset_platform_id(chain_id)
    mapped_addresses = [LEGACY_MAPPINGS.get(a.lower(), a) for a in addresses]
    coin_ids = get_coin_ids(mapped_addresses, asset_platform_id)
    formatted_ids = ",".join(coin_ids)
    base_url = "https://api.coingecko.com/api/v3/simple/price"
    url = f"{base_url}?ids={formatted_ids}&vs_currencies=usd"
    r = requests.get(url)
    r.raise_for_status()
    results = r.json()
    return {a: results[cid]["usd"] for a, cid in zip(addresses, coin_ids)}
