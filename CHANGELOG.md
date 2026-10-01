# Changelog

## 0.1.0: first public release

- Synthetic wealth-domain document generator (`ppm`, `lpa`, `ddq`, `adv`, `k1`, `capital_account`, `ic_memo`) from one seeded world state
- Labeled flaw injection: `contradiction`, `arithmetic_error`, `ungrounded_claim`
- Oracle checker (`check_consistency`) plus two world-free detectors (`detect_naive`, `detect_worldfree`) scored against the answer key
- `eval/eval.py` regression suite (36 checks): 201-seed range, negative `lp_allocated_gain` seeds, naive-vs-worldfree precision head-to-head
- Packaging via `pyproject.toml` (`pip install -e .`); CI runs `eval/eval.py` and `run_demo.py` on every push/PR and greps stdout for the quoted numbers
- `check_consistency(corpus)`: one-argument form, world rebuilt from the recorded seed
- Provable seed mismatch raises `ValueError`; bare `(docs, world)` form emits a `UserWarning`
- `pytest`-discoverable `tests/`, `console_scripts` entry points (`synthfin-demo`, `synthfin-eval`)
- CI matrix: Python 3.9-3.12
