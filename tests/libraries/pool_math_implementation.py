from typing import Iterable

from tests.support.quantized_decimal import QuantizedDecimal as D


def liquidityInvariantUpdate(
    balances: Iterable[D],
    lastInvariant: D,
    deltaBalances: Iterable[D],
    isIncreaseLiq: bool,
) -> D:

    largest_balance = 0
    for balance in balances:
        if balance > largest_balance:
            largest_balance = balance

    index_of_largest_balance = balances.index(largest_balance)

    delta_invariant = (
        deltaBalances[index_of_largest_balance] / largest_balance * lastInvariant
    )

    if isIncreaseLiq == True:
        invariant = lastInvariant + delta_invariant
    else:
        invariant = lastInvariant - delta_invariant
    return invariant
