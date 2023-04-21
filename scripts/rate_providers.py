
from brownie import *
from decimal import Decimal

# This has to be run from inside brownie with the appropriate network.

def get_rates(rate_provider_addresses) -> list[Decimal]:
    """Get rates from a list of IRateProvider addresses."""
    ret = []
    for address in rate_provider_addresses:
        if address:
            c = interfaces.IRateProvider.at(address)
            rate = c.getRate()
            # Rates are always 18-decimal.
            ret.append(Decimal(rate) / Decimal(10**18))
        else:
            ret.append(Decimal(1))
    return ret

