from collections import OrderedDict
from pprint import pprint

from brownie import *
from toolz import keyfilter, valmap, second, merge

from tests.support.quantized_decimal import QuantizedDecimal as D
from tests.cpmmv3 import v3_math_implementation as math_implementation

# See test_three_pool_properties.py
from tests.support.utils import scale, unscale

Decimal = D

import tabulate as tabulatemod


def tabulate(*args, **kwargs):
    kwargs.setdefault("disable_numparse", True)
    return tabulatemod.tabulate(*args, **kwargs)


def dstr(x):
    """Exact representation of a decimal, without fluff; fallback str()"""
    if isinstance(x, D):
        return repr(x)[9:-2]
    return str(x)
    # return repr(x)


def main():
    # args = (
    #     (D('16743757275.452039152786685295'),
    #      D('1967668306.780847696789534899'),
    #      D('396788946.610986231634363959')),
    #     D('3812260336.851356457000000000'),
    #     D('0.200000000181790486'))
    # args = ((Decimal('9168.743605294506949000'),
    #          Decimal('0.091687436052945069'),
    #          Decimal('38.996868460619872727')),
    #         Decimal('512.421100000000000000'),
    #         Decimal('0.200000000000000000'))
    # args = ((Decimal('49686401536.877547376241868523'),
    #          Decimal('496864.015368775473762418'),
    #          Decimal('6569625536.505956832858269387')),
    #         Decimal('85213789318.792422523679329140'),
    #         Decimal('0.809675172621428571'))
    # args=((Decimal('3771.913533471116339351'),
    #   Decimal('0.037719135334711232'),
    #   Decimal('3.368163082086836003')),
    #  Decimal('167.693180000000000000'),
    #  Decimal('0.200000000784289200'))
    # args=((Decimal('418054146508.371907703454806905'),
    #   Decimal('4180541.465083719077035275'),
    #   Decimal('8093420577.572500732737759983')),
    #  Decimal('36100449536.057415199000000000'),
    #  Decimal('0.200000000061207609'))
    # args = ((Decimal('1.000000000000000000'),
    #          Decimal('1.000000000000001896'),
    #          Decimal('130.896398441663402525')),
    #         Decimal('11.163542800000000000'),
    #         Decimal('0.200000000000478659'))
    # args=((Decimal('728109563488.263687529903349137'),
    #   Decimal('7281095.634882636875299036'),
    #   Decimal('1724716619.689367265339564601')),
    #  Decimal('36417643407.707023648100000000'),
    #  Decimal('0.200000000021982758'))
    # args = ((Decimal('10.000000000000000000'),
    #          Decimal('23.181541716675501365'),
    #          Decimal('26.188711041986014369')),
    #         Decimal('31046.278348833000000000'),
    #         Decimal('0.999362587428787313'))
    args = (
        [
            Decimal("1029444269637.250423547829820659"),
            Decimal("0E-18"),
            Decimal("0E-18"),
        ],
        Decimal("41509849622.621794054000000000"),
        Decimal("0.200000000096340603"),
    )

    balances, invariant, root3Alpha = args

    a, mb, mc, md = math_implementation.calculateCubicTerms(balances, root3Alpha)

    invariant_math, log_math = math_implementation.calculateInvariantNewton(
        a, mb, mc, md, root3Alpha, balances
    )

    # TODO Gyro3CLPMathDebug is slightly out of sync with Gyro3CLPMath. So this is all a bit outdated.
    gyro_three_math_testing = accounts[0].deploy(Gyro3CLPMathDebug)

    tx = gyro_three_math_testing._calculateInvariantUnderOver(
        scale(balances), scale(root3Alpha)
    )
    invariant_sol_under, under_is_under, invariant_sol_over = unscale(tx.return_value)
    assert under_is_under

    tx1 = gyro_three_math_testing._calculateCubicTerms(
        scale(balances), scale(root3Alpha)
    )
    a1, mb1, mc1, md1 = unscale(tx1.return_value)

    start_sol = unscale(
        gyro_three_math_testing._calculateCubicStartingPoint(
            *scale((a, mb, mc, md))
        ).return_value
    )

    ls = locals()
    print(
        tabulate(
            [
                (k, dstr(ls[k]))
                for k in "invariant invariant_math invariant_sol_under invariant_sol_over start_sol".split()
            ]
        )
    )

    def onix(i, f):
        def ret(t):
            tl = list(t)
            tl[i] = f(tl[i])
            return type(t)(tl)

        return ret

    def curmap(f):
        return lambda lst: map(f, lst)

    print("\n")
    print(
        tabulate(
            map(
                onix(1, dstr),
                [
                    ("err rel python", invariant_math / invariant - 1),
                    ("err rel sol under", invariant_sol_under / invariant - 1),
                    ("err rel sol over", invariant_sol_over / invariant - 1),
                    ("err rel sol starting", start_sol / invariant - 1),
                ],
            )
        )
    )

    print("\n")
    print(
        tabulate(
            map(
                curmap(dstr),
                [
                    ("a", a, a1),
                    ("mb", mb, mb1),
                    ("mc", mc, mc1),
                    ("md", md, md1),
                ],
            ),
            headers=("", "Python", "Solidity"),
        )
    )

    print("\n----- Python: -----\n")
    # pprint(log_math)
    keys = ["l", "delta"]
    print(tabulate([[dstr(e[k]) for k in keys] for e in log_math], headers=keys))

    print("\n----- Solidity: -----\n")
    if "NewtonStep" in tx.events:
        # True unless we're in the lower-order special case.
        keys = ["l", "deltaAbs"]
        # pprint([valmap(unscale, e) for e in tx.events['NewtonStep']])
        print(
            tabulate(
                [
                    [dstr(unscale(e[k])) for k in keys] + [e["deltaIsPos"]]
                    for e in tx.events["NewtonStep"]
                ],
                headers=keys + ["is pos"],
            )
        )

    print(f"\nGas used (Solidity): {tx.gas_used}")
