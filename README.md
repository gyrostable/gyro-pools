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

## Gas Testing

To analyze gas usage, the `Tracer` in `tests/support/analyze_trace.py` can be used in the following way:

```python
from tests.support.trace_analyzer import Tracer

tx = ... # transaction to analyze

tracer = Tracer.load()
print(tracer.trace_tx(tx))
```

For this to work, you need to install a version of brownie where a bug has been fixed:
```bash
$ pip install -U git+https://github.com/danhper/brownie.git@avoid-removing-dependencies
```

Then you need to run your script with everything compiled *before* the script runs, i.e., you need something like

```bash
brownie compile; brownie run scripts/my_script.py
```
