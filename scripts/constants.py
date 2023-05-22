from os import path

CONFIG_PATH = path.join(path.dirname(path.dirname(__file__)), "config")

BALANCER_ADDRESSES = {
    137: {
        "query_processor": "0x72D07D7DcA67b8A406aD1Ec34ce969c90bFEE768",
        "vault": "0xBA12222222228d8Ba445958a75a0704d566BF2C8",
    },
    1337: {
        "query_processor": "0xCfEB869F69431e42cdB54A4F4f105C19C080A601",
        "vault": "0xD833215cBcc3f914bD1C9ece3EE7BF8B14f841bb",
    },
    42: {
        "vault": "0xBA12222222228d8Ba445958a75a0704d566BF2C8",
        "query_processor": "0x41c7523aA9b369a65983C0ff719B81947B07fc5c",
    },
    10: {
        "query_processor": "0xD7FAD3bd59D6477cbe1BE7f646F7f1BA25b230f8",
        "vault": "0xBA12222222228d8Ba445958a75a0704d566BF2C8",
    },
    5: {
        "vault": "0xBA12222222228d8Ba445958a75a0704d566BF2C8",
        "query_processor": "0xF949645042a607fa260D932DF999FE8A02B86247",
    },
}

GYROSCOPE_ADDRESSES = {
    137: {
        "gyro_config": "0xFdc2e9E03f515804744A40d0f8d25C16e93fbE67",
        "proxy_admin": "0x83d34ca335d197bcFe403cb38E82CBD734C4CbBE",
    },
    1337: {
        "proxy_admin": "0x90F8bf6A479f320ead074411a4B0e7944Ea8c9C1",
        "gyro_config": "0xe78A0F7E598Cc8b0Bb87894B0F60dD2a88d6a8Ab",
    },
    42: {"gyro_config": "0x402519E6cc733893af5fFf40e26397268769CBc3"},
    5: {"gyro_config": "0xfd5E29d7B36d0AfD4cb8A0AFAB5F360d21dE5C63"},
    10: {
        "gyro_config": "0x32Acb44fC929339b9F16F0449525cC590D2a23F3",
        "proxy_admin": "0x00A2a9BBD352Ab46274433FAA9Fec35fE3aBB4a8",
    },
}

POOL_OWNER = {
    137: "0xEf63C5ceDEc9d53911162BEd5cE8956AE570387B",
    1337: "0x90F8bf6A479f320ead074411a4B0e7944Ea8c9C1",
    10: "0x8c1ce9CfD579A26D86Fd7c2fA980c28AC4C7B282",
}

PAUSE_MANAGER = {
    137: "0x148b36E4F96914550145b72E9Dbcd514048CafED",
    1337: "0x90F8bf6A479f320ead074411a4B0e7944Ea8c9C1",
    10: "0x8c1ce9CfD579A26D86Fd7c2fA980c28AC4C7B282",
}

DEPLOYED_POOLS = {
    137: {
        "c2lp": "0xF353BE94205776387C0C8162B424806B00FCA93F00020000000000000000045F",
        "c3lp": "0xBC9BC9DC07A3C860DA97693D94B0F12D6DCCF4B1000100000000000000000460",
    }
}

DEPLOYED_FACTORIES = {
    1337: {
        "eclp": "0xe982E462b094850F12AF94d21D470e21bE9D0E9C",
    },
    137: {
        "c2lp": "0x5d8545a7330245150bE0Ce88F8afB0EDc41dFc34",
        "c3lp": "0x90f08B3705208E41DbEEB37A42Fb628dD483AdDa",
        "eclp": "0x1a79A24Db0F73e9087205287761fC9C5C305926b",
    },
    10: {"eclp": "0x9b683cA24B0e013512E2566b68704dBe9677413c"},
    42: {"eclp": "0xd0E45cf9e4E7008B78e679F46778bb28C2e8a5Eb"},
    5: {"eclp": "0xeEe2e20C97633f473A063e3de4807f3F974DBC6c"},
}


DECIMALS = {
    "USDC": 6,
    "USDT": 6,
    "BTC": 8,
    "WBTC": 8,
    "ETH": 18,
    "WETH": 18,
    "DAI": 18,
    "BUSD": 18,
    "TUSD": 18,
    "WMATIC": 18,
    "stMATIC": 18,
}

STABLE_COINS = ["DAI", "USDT", "USDC", "GUSD", "HUSD", "TUSD", "USDP", "LUSD"]

TOKEN_ADDRESSES = {
    1: {
        "DAI": "0x6B175474E89094C44Da98b954EedeAC495271d0F",
        "WBTC": "0x2260FAC5E5542a773Aa44fBCfeDf7C193bc2C599",
        "USDC": "0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48",
        "WETH": "0xC02aaA39b223FE8D0A0e5C4F27eAD9083C756Cc2",
        "CRV": "0xD533a949740bb3306d119CC777fa900bA034cd52",
        "TUSD": "0x0000000000085d4780B73119b644AE5ecd22b376",
        "USDP": "0x8E870D67F660D95d5be530380D0eC0bd388289E1",
        "PAXG": "0x45804880De22913dAFE09f4980848ECE6EcbAf78",
        "AAVE": "0x7Fc66500c84A76Ad7e9c93437bFc5Ac33E2DDaE9",
        "LUSD": "0x5f98805A4E8be255a32880FDeC7F6728C6568bA0",
        "COMP": "0xc00e94Cb662C3520282E6f5717214004A7f26888",
        "USDT": "0xdAC17F958D2ee523a2206206994597C13D831ec7",
        "GUSD": "0x056Fd409E1d7A124BD7017459dFEa2F387b6d5Cd",
        "HUSD": "0xdF574c24545E5FfEcb9a659c229253D4111d87e1",
    },
    10: {
        "USDC": "0x7F5c764cBc14f9669B88837ca1490cCa17c31607",
        "USDT": "0x94b008aa00579c1307b0ef2c499ad98a8ce58e58",
    },
    137: {
        "DAI": "0x8f3Cf7ad23Cd3CaDbD9735AFf958023239c6A063",
        "WBTC": "0x1BFD67037B42Cf73acF2047067bd4F2C47D9BfD6",
        "USDC": "0x2791Bca1f2de4661ED88A30C99A7a9449Aa84174",
        "WETH": "0x7ceB23fD6bC0adD59E62ac25578270cFf1b9f619",
        "CRV": "0x172370d5Cd63279eFa6d502DAB29171933a610AF",
        "TUSD": "0x2e1AD108fF1D8C782fcBbB89AAd783aC49586756",
        "PAXG": "0x553d3D295e0f695B9228246232eDF400ed3560B5",
        "AAVE": "0xD6DF932A45C0f255f85145f286eA0b292B21C90B",
        "COMP": "0x8505b9d2254A7Ae468c0E9dd10Ccea3A837aef5c",
        "USDT": "0xc2132D05D31c914a87C6611C10748AEb04B58e8F",
        "GUSD": "0xC8A94a3d3D2dabC3C1CaffFFDcA6A7543c3e3e65",
        "HUSD": "0x2088C47Fc0c78356c622F79dBa4CbE1cCfA84A91",
        "BUSD": "0x9C9e5fD8bbc25984B178FdCE6117Defa39d2db39",
        "WMATIC": "0x0d500B1d8E8eF31E21C99d1Db9A6444d3ADf1270",
        "stMATIC": "0x3A58a54C066FdC0f2D55FC9C89F0415C92eBf3C4",
    },
}

# For testing. map.json should in principle work, too, but Steffen doesn't trust it sorry.
TEST_CONST_RATE_PROVIDER_POLYGON = "0xC707205b3cFf2df873811F19f789648286AbB85e"
