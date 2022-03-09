def calculateInvariantUnderOver(gyro_three_math_testing, balances, root3Alpha):
    """Use like gyro_three_math_testing; we assert that we actually get an underestimate. No scaling is done."""
    # Calling as transaction to get more debug info.
    # For example: run `brownie test` with `-I` and look at `history[-1].call_trace()`.
    tx = gyro_three_math_testing.calculateInvariantUnderOver.transact(balances, root3Alpha)
    l_under, under_is_under, l_over = tx.return_value
    assert under_is_under
    return l_under, l_over