# synth-corpus

If you're building a tool that's supposed to catch errors or contradictions in financial
paperwork, you need test data where the problems are already known, so you can measure whether
the tool actually finds them. **synth-corpus** generates realistic-looking sets of fund
documents that all trace back to one consistent underlying "world," then plants defects on
purpose (a contradiction between two documents, an arithmetic error, a claim with no supporting
evidence) and records exactly where each one is. That record is the ground truth: an answer key
of every planted defect and its location, which any downstream detector can be scored against.
Generation is deterministic and runs offline. This produces test data, not real filings.

## Quickstart

```
pip install -e .
python eval/eval.py     # 36/36 checks, exit 0
python run_demo.py      # writes out/clean + out/flawed
```

The only dependency is numpy (seeded, for reproducibility), pinned in `pyproject.toml`
(`numpy>=1.24,<3`). Documents are templated markdown; the manifest is JSON.

## What it produces

Calling `generate(seed, injects=[...])` returns a `Corpus` with two fields, `docs` and
`manifest`.

`docs` holds seven documents — `ppm, lpa, ddq, adv, k1, capital_account, ic_memo` (an offering
memo, a limited partnership agreement, a due-diligence questionnaire, a Form ADV, a K-1 tax
form, a capital-account statement, and an investment-committee memo) — all drawn from one
wealth-management (WM) alternatives-diligence world.

`manifest` holds `{seed, world, flaws}`: `seed` is the integer that produced `docs`; `world` is
`World.summary()`, a plain dict for display and inspection, not a `World` instance; `flaws` is
the list of injected flaws, the answer key.

### Scoring a corpus (safe by construction)

`check_consistency` is a reference oracle: a checker that already knows the fund's true values,
so it isn't really detecting anything blind. It confirms the documents are internally
consistent, and later serves as the benchmark other detectors are measured against. It only
gives correct results if it's checking the same `World` that produced the documents — otherwise
it fabricates plausible-looking findings. The safe way to call it is to pass the `Corpus` itself
and let it rebuild the world from the corpus's own recorded seed. That pairing can't be
mismatched:

```python
c = generate(20260704, injects=[{"type": "contradiction", "doc": "ddq", "field": "management_fee"}])
findings = check_consistency(c)   # preferred: world rebuilt from c.manifest['seed']; cannot mismatch
```

Full set of accepted forms and their safety semantics (see `synthfin/check.py`'s docstring):

| Call | Behavior |
|---|---|
| `check_consistency(c)` | Preferred. World derived from `c.manifest['seed']`; a mismatch is impossible. |
| `check_consistency(c, world_or_manifest)` | Both sides carry a seed, so they're cross-checked; a true mismatch raises `ValueError`. |
| `check_consistency(c.docs, build_world(seed))` | A bare `docs` dict carries no seed, so the pairing is unverifiable and emits a `UserWarning` every time — passing the wrong seed here is the classic silent-wrong hazard, so it warns loudly rather than returning a fabricated set. |
| `check_consistency(c.docs)` | Raises `ValueError` — no seed to derive a world from. |

After persisting `manifest.json` and reloading it, re-score safely by rebuilding the `Corpus`
(or by regenerating with `generate(manifest['seed'])`) and using the one-arg form, or by passing
the reloaded manifest alongside the corpus so both seeds are cross-checked:

```python
findings = check_consistency(c, reloaded_manifest)   # both seeds present → verified, no warning
```

## Flaw types (labeled)

- `contradiction` — a canonical figure (the one correct value for something like the management
  fee, which should match everywhere it appears) disagrees between a document and the world, or
  between two documents.
- `arithmetic_error` — the capital-account rollforward (the running math that adds
  contributions, subtracts distributions, and arrives at an ending balance) stops summing to the
  stated NAV (net asset value).
- `ungrounded_claim` — a metric in the investment-committee memo with no support anywhere else
  in the corpus.

One naming quirk worth knowing: `manifest["flaws"]` (the answer key, written by `inject.py`)
records this type as `arithmetic_error`, while the findings from `check_consistency` and
`detect_worldfree` (written by `check.py`) name the same defect `arithmetic`, matching the
general `contradiction`/`arithmetic` naming the checker uses throughout. The two vocabularies
are kept separate on purpose — renaming either would break integrators who already key off one
or the other. A tool comparing findings against the answer key has to map `arithmetic_error`
(flaw type) to `arithmetic` (finding type) itself; see `_key()` in `eval/eval.py` for the
reference mapping.

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

## Measured (eval.py, exit 0 — 36/36)

A clean corpus ties out (0 findings, 0 flaws, arithmetic ties, all 7 docs present), and injected
flaws are labeled and detected at exactly their locations
(`contradiction_labels_match_detections`). This is checked across a 201-seed range, including 21
seeds where a negative `lp_allocated_gain` occurs (a fund posting a loss renders, for example,
`"Allocated net gain: $-2,650,000"`), not just one hand-picked seed. Every canonical figure
(`management_fee`, `carried_interest`, `hurdle`, `fund_size`, `lp_commitment`, `distributions`,
`ending_nav`) has its own contradiction-detection round trip. Generation is reproducible: the
same seed and injects produce byte-identical docs and manifest.

### World-free detector vs a naive baseline (measured head-to-head)

`check_consistency(docs, world)` is a reference oracle. It's handed the world it grades against,
so passing it proves nothing about how hard the defects are to find. To show the harness
actually scores detectors and not just the oracle, two world-free detectors (they compare
documents to each other, never to the world's true values) are scored against the labeled
answer key on a corpus with three contradictions that can be isolated and one arithmetic break:

- `detect_naive(docs)` — a competent-but-naive baseline: on any cross-document disagreement, it
  flags every document carrying that figure. The conflict is real, but it can't name the
  culprit.
- `detect_worldfree(docs)` — takes a majority vote to isolate the odd one out, and re-derives
  the capital-account rollforward from its own lines.

The table below scores each detector by precision (of the things it flagged, how many were real
defects), recall (of the real defects, how many it caught), and F1 (a single score combining the
two):

| detector | precision | recall | F1 | TP | FP | FN |
|---|---|---|---|---|---|---|
| oracle (reads world) | 1.000 | 1.000 | 1.000 | 4 | 0 | 0 |
| worldfree (no world) | 1.000 | 1.000 | 1.000 | 4 | 0 | 0 |
| naive baseline | 0.364 | 1.000 | 0.533 | 4 | 7 | 0 |

Both detectors find every real flaw (recall 1.000), but the naive baseline over-flags 7 innocent
documents (precision 0.364), while the consensus detector isolates exactly the deviating
document (precision 1.000) — a measured precision gap of 0.636 — and reaches the same
answer-key set as the world-reading oracle without ever reading the world
(`worldfree_matches_oracle`). [Measured on one seed, 20260704; all figures are printed by
`eval/eval.py`.] Majority-vote isolation requires a figure to appear in ≥3 documents; on a
2-doc disagreement, `detect_worldfree` honestly falls back to flagging both, since there's no
majority to arbitrate.

## Honest scope

This release covers one WM alternatives-diligence world. Documents are templated, not
LLM-generated: figures are internally consistent and plausible, but the paperwork doesn't have
full regulatory depth. The structural checker catches numeric contradictions and arithmetic
breaks. Semantic or ungrounded flaws, like an unsupported claim, aren't caught by this checker —
they're labeled instead, so a downstream red-team (a separate detector built to catch exactly
this kind of thing) can be scored against them. Support for hedge-fund and VC worlds would come
from adding new world states and renderers.

## Where it fits

This is meant as a foundation other tools can build on: anything that needs labeled corpora with
known answers, so it can be built and scored honestly. Examples include a decision red-team, or
a document-grounding defense for a RAG system (a tool that answers questions by pulling in and
citing source documents).

## License

MIT — see [LICENSE](LICENSE).
