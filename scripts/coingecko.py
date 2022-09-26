from typing import Dict, List

import requests


LEGACY_MAPPINGS = {
    "0x9c9e5fd8bbc25984b178fdce6117defa39d2db39": "0xdab529f40e671a1d4bf91361c21bf9f0c9712ab7",
}


def get_asset_platforms():
    r = requests.get("https://api.coingecko.com/api/v3/asset_platforms")
    r.raise_for_status()
    return r.json()


def get_asset_platform_id(chain_id: int) -> str:
    asset_platforms = get_asset_platforms()
    for asset_platform in asset_platforms:
        if asset_platform["chain_identifier"] == chain_id:
            return asset_platform["id"]
    raise ValueError(f"could not find asset platform for chain id {chain_id}")


def get_prices(addresses: List[str], chain_id: int = 1) -> Dict[str, float]:
    asset_platform_id = get_asset_platform_id(chain_id)
    mapped_addresses = [LEGACY_MAPPINGS.get(a.lower(), a) for a in addresses]
    contract_addresses = ",".join(mapped_addresses)
    base_url = "https://api.coingecko.com/api/v3/simple/token_price"
    url = f"{base_url}/{asset_platform_id}?contract_addresses={contract_addresses}&vs_currencies=usd"
    r = requests.get(url)
    r.raise_for_status()
    results = r.json()
    return {a: results[ma.lower()]["usd"] for a, ma in zip(addresses, mapped_addresses)}
