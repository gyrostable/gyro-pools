# Gyroscope Vaults

Gyroscope vaults based on Balancer V2.

This project uses Brownie as its main testing framework but is also
compatible with hardhat to be able to reuse some of the Balancer testing
infrastructure if needed.


## Compiling and testing

The project can be compiled and tested using

```
brownie compile
brownie test
```

## Testing

To analyze gas usage, the `Tracer` in `tests/support/analyze_trace.py` can be used in the following way:


```python
from tests.support.trace_analzyer import Tracer

tx = ... # transaction to analyze

tracer = Tracer.load()
tracer.trace_tx(tx)
```
