from decimal import Decimal
from typing import Tuple

import hypothesis.strategies as st
import pytest
from brownie.test import given
from tests.support.utils import scale, to_decimal

def gen_root3Alpha():
    return st.decimals()
