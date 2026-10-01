# synth-corpus

Synthetic fund-document corpora with planted, labeled defects, plus **redteam**, a detector scored against them.

- Generates fund documents from one consistent seeded "world"
- Plants defects: contradiction, arithmetic error, ungrounded claim
- Records each defect and its location: the answer key
- Deterministic, offline
- Test data, not real filings

redteam flags cross-document contradictions, unsupported performance claims, and arithmetic that doesn't reconcile.

## Headline score

- redteam: recall 1.000, precision 1.000 against this corpus
- Flaw types mapped one-to-one onto detectors (`eval/eval_redteam.py`)
- No unanticipated defects tested

## Quickstart

```
pip install -e .
python eval/eval.py            # corpus generator: 36/36 checks, exit 0
python run_demo.py             # writes out/clean + out/flawed
python eval/eval_redteam.py    # detector scored against the answer key
python run_redteam_demo.py     # one flawed corpus, scored end to end
pytest -q                      # 33 tests
```

Only dependency: numpy (`numpy>=1.24,<3`, pinned in `pyproject.toml`). Documents are templated markdown; the manifest is JSON.

## What it produces

`generate(seed, injects=[...])` returns a `Corpus` with `docs` and `manifest`.

`docs`: seven documents from one wealth-management (WM) alternatives-diligence world.

- `ppm`: offering memo
- `lpa`: limited partnership agreement
- `ddq`: due-diligence questionnaire
- `adv`: Form ADV
- `k1`: K-1 tax form
- `capital_account`: capital-account statement
- `ic_memo`: investment-committee memo

`manifest`: `{seed, world, flaws}`

- `seed`: integer that produced `docs`
- `world`: `World.summary()`, a plain dict
- `flaws`: injected flaws, the answer key

### Scoring a corpus

`check_consistency` is a reference oracle.

- Knows the true values
- Wrong `World` gives fabricated findings

Pass the `Corpus` and it rebuilds the world from the recorded seed:

```python
c = generate(20260704, injects=[{"type": "contradiction", "doc": "ddq", "field": "management_fee"}])
findings = check_consistency(c)   # preferred: world rebuilt from c.manifest['seed']; cannot mismatch
```

Accepted forms (see `synthfin/check.py`'s docstring):

| Call | Behavior |
|---|---|
| `check_consistency(c)` | Preferred. World derived from `c.manifest['seed']`; a mismatch is impossible. |
| `check_consistency(c, world_or_manifest)` | Both sides carry a seed, so they're cross-checked; a true mismatch raises `ValueError`. |
| `check_consistency(c.docs, build_world(seed))` | A bare `docs` dict carries no seed, so the pairing is unverifiable and emits a `UserWarning` every time. |
| `check_consistency(c.docs)` | Raises `ValueError`: no seed to derive a world from. |

After reloading `manifest.json`, rebuild the `Corpus` (or `generate(manifest['seed'])`) and use the one-arg form, or pass the reloaded manifest alongside the corpus:

```python
findings = check_consistency(c, reloaded_manifest)   # both seeds present → verified, no warning
```

## Flaw types

- `contradiction`: a canonical figure (e.g. management fee) disagrees between a document and the world, or between two documents
- `arithmetic_error`: the capital-account rollforward stops summing to the stated NAV (net asset value)
- `ungrounded_claim`: a metric in the investment-committee memo with no support elsewhere in the corpus

Naming: `manifest["flaws"]` (from `inject.py`) uses `arithmetic_error`. Findings from `check_consistency` and `detect_worldfree` (from `check.py`) use `arithmetic`. A tool comparing the two maps between them; see `_key()` in `eval/eval.py`.

```python
from synthfin import generate, check_consistency, build_world
c = generate(20260704, injects=[
    {"type": "contradiction", "doc": "ddq", "field": "management_fee"},
    {"type": "arithmetic_error"},
    {"type": "ungrounded_claim"},
])
findings = check_consistency(c)                               # structural detections (mismatch-proof)
answer_key = c.manifest["flaws"]                              # ground truth to score against
```

## Measured (eval.py, exit 0, 36/36)

- Clean corpus: 0 findings, 0 flaws, arithmetic ties, all 7 docs present
- Injected flaws labeled and detected at exactly their locations (`contradiction_labels_match_detections`)
- Checked across a 201-seed range, including 21 seeds with a negative `lp_allocated_gain` (renders e.g. `"Allocated net gain: $-2,650,000"`)
- Each canonical figure (`management_fee`, `carried_interest`, `hurdle`, `fund_size`, `lp_commitment`, `distributions`, `ending_nav`) has its own contradiction round trip
- Same seed and injects: byte-identical docs and manifest

### World-free detector vs a naive baseline

Two world-free detectors, scored against the answer key on a corpus with three isolatable contradictions and one arithmetic break:

- `detect_naive(docs)`: on any cross-document disagreement, flags every document carrying that figure
- `detect_worldfree(docs)`: majority vote isolates the odd one out; re-derives the capital-account rollforward from its own lines

| detector | precision | recall | F1 | TP | FP | FN |
|---|---|---|---|---|---|---|
| oracle (reads world) | 1.000 | 1.000 | 1.000 | 4 | 0 | 0 |
| worldfree (no world) | 1.000 | 1.000 | 1.000 | 4 | 0 | 0 |
| naive baseline | 0.364 | 1.000 | 0.533 | 4 | 7 | 0 |

- Precision gap: 0.636
- `detect_worldfree` matches the oracle's answer-key set without reading the world (`worldfree_matches_oracle`)
- One seed, 20260704; figures printed by `eval/eval.py`
- Majority vote needs a figure in 3 or more documents; on a 2-doc disagreement `detect_worldfree` flags both

## Measured: the detector vs a naive baseline

Same seeds, same packets, scored against the answer key (`python eval/eval_redteam.py`):

| detector | recall | precision | false positives on clean docs |
|---|---|---|---|
| deterministic (this tool) | 1.000 | 1.000 | 0 |
| naive keyword baseline | 0.667 | 0.240 | 19 |

`scripts/check_readme_numbers.py` re-runs the eval and fails if this table drifts.

## Coverage and limits

- One WM alternatives-diligence world
- Documents are templated, not LLM-generated; no full regulatory depth
- Structural checker catches numeric contradictions and arithmetic breaks
- Ungrounded claims are labeled, not caught by the checker
- Hedge-fund and VC worlds would need new world states and renderers

## Where it fits

- Foundation for anything that needs labeled corpora with known answers
- `redteam/`: decision red-team that checks an AI-generated investment recommendation against its sources
- Document-grounding defense for a RAG system
- `redteam` began as its own repository; merged here with full commit history

## License

MIT. See [LICENSE](LICENSE).
