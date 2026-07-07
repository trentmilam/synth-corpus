# Contributing

## Running the checks

```
pip install -e .
python eval/eval.py     # regression + measured checks, exit 0 on success
python run_demo.py      # writes out/clean + out/flawed and prints the answer key
```

`eval/eval.py` is the source of truth for every number quoted in the README (check count,
precision/recall, the naive-vs-worldfree precision gap). If you change `synthfin/`, re-run it and
update the README numbers to match — do not hand-edit README figures without a run to back them.

## Adding a flaw type

Flaw types live in `synthfin/inject.py` (`apply_injects`). Each one must:

1. Mutate a real, present figure or line — reject no-op injections (see the existing `ValueError`
   guards for examples: missing label, injected value equal to truth, zero-delta arithmetic error).
2. Return a label dict with at least `{type, doc, field, truth, injected}` so downstream tools can
   score against it.
3. Get a round-trip test in `eval/eval.py`: inject it, run the relevant checker, and assert the
   flaw is detected at exactly its labeled location.

## Adding a canonical figure

Canonical figures live in `synthfin/check.py`'s `FIELDS` dict and are rendered via a label constant
in `synthfin/render.py`. If you add one, add a contradiction round-trip test for it in `eval/eval.py`
(see the loop over `fund_size`, `hurdle`, `distributions`, `ending_nav` for the pattern) — an
untested field can silently regress without failing "N/N checks".
