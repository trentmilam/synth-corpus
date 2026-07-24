# Changelog

All notable changes to this project are documented in this file.

## 0.1.0 — first public release

- Synthetic wealth-domain document generator (`ppm`, `lpa`, `ddq`, `adv`, `k1`, `capital_account`,
  `ic_memo`) rendered from one seeded, internally-consistent world state.
- Labeled flaw injection: `contradiction`, `arithmetic_error`, `ungrounded_claim`.
- Oracle consistency checker (`check_consistency`) plus two world-free detectors (`detect_naive`,
  `detect_worldfree`) scored against the labeled answer key.
- `eval/eval.py` regression suite (36 checks) covering a 201-seed range, including seeds with a
  negative `lp_allocated_gain`, plus a measured naive-vs-worldfree precision head-to-head.
- Packaging via `pyproject.toml` (`pip install -e .`); CI runs `eval/eval.py` and `run_demo.py` on
  every push/PR and greps stdout for the numbers this README quotes.
- `check_consistency()` gains a mismatch-proof one-argument form — `check_consistency(corpus)` —
  that rebuilds the world from the corpus's own recorded seed. A provable seed mismatch raises
  `ValueError`; the unverifiable bare `(docs, world)` form now emits a `UserWarning`.
- `pytest`-discoverable `tests/`, `console_scripts` entry points (`synthfin-demo`, `synthfin-eval`),
  and a CI matrix across Python 3.9–3.12.
