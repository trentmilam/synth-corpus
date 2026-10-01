# Contributing

## Checks

```
pip install -e .
python eval/eval.py     # regression + measured checks, exit 0 on success
python run_demo.py      # writes out/clean + out/flawed and prints the answer key
```

`eval/eval.py` is the source for every README number. After changing `synthfin/`, re-run it and update the README.

## Adding a flaw type

Flaw types live in `synthfin/inject.py` (`apply_injects`). Each one:

1. Mutates a real, present figure or line; rejects no-op injections (see the existing `ValueError` guards)
2. Returns a label dict with at least `{type, doc, field, truth, injected}`
3. Gets a round-trip test in `eval/eval.py`: inject, run the checker, assert detection at the labeled location

## Adding a canonical figure

Canonical figures live in `synthfin/check.py`'s `FIELDS` dict, rendered via a label constant in `synthfin/render.py`. Add a contradiction round-trip test in `eval/eval.py` (pattern: the loop over `fund_size`, `hurdle`, `distributions`, `ending_nav`).
