from decimal import Decimal
from typing import List


def compute_bounds_sqrts(tokens: List[str], raw_bounds: List[str]):
    bounds = [Decimal(b) for b in raw_bounds]
    if tokens[0].lower() > tokens[1].lower():
        bounds = [1 / bounds[1], 1 / bounds[0]]
    sqrts = [b.sqrt() for b in bounds]
    return sqrts
