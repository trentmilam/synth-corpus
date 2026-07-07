# synth-corpus — synthetic financial corpus generator (labeled test-harness)

Generate realistic wealth-domain document sets **with a ground-truth answer key**. Every document
renders from one internally-consistent world state (so a fund's PPM ↔ LPA ↔ DDQ ↔ ADV ↔
capital-account ↔ K-1 ↔ IC memo all tie out), and a flaw-injection layer plants **labeled** defects
so any downstream tool can be scored against known truth. Deterministic + offline. For testing only.

## Quickstart

```
pip install -e .
python eval/eval.py     # 36/36 checks, exit 0
python run_demo.py      # writes out/clean + out/flawed
```

Only dependency is numpy (seeded), pinned in `pyproject.toml` (`numpy>=1.24,<3`). Documents are
templated markdown; the manifest is JSON.

## What it produces

A `Corpus{docs, manifest}` from `generate(seed, injects=[...])`:

- **docs** — `ppm, lpa, ddq, adv, k1, capital_account, ic_memo` (a WM alternatives-diligence world).
- **manifest** — `{seed, world, flaws}`: `seed` is the integer that produced `docs`; `world` is
  `World.summary()` — a **plain dict**, display/inspection data, not a `World` instance — and
  `flaws` is the list of injected flaws (the answer key).

### Scoring a corpus (safe by construction)

`check_consistency` is a reference oracle — it must be graded against the exact `World` that
produced the documents, or it fabricates plausible-looking findings. **Pass the `Corpus` and let
it derive the world from the corpus's own recorded seed** — this is mismatch-proof:

```python
c = generate(20260704, injects=[{"type": "contradiction", "doc": "ddq", "field": "management_fee"}])
findings = check_consistency(c)   # preferred: world rebuilt from c.manifest['seed']; cannot mismatch
```

Full set of accepted forms and their safety semantics (see `synthfin/check.py`'s docstring):

| Call | Behavior |
|---|---|
| `check_consistency(c)` | **Preferred.** World derived from `c.manifest['seed']`; mismatch is impossible. |
| `check_consistency(c, world_or_manifest)` | Both sides carry a seed → cross-checked; a true mismatch **raises `ValueError`**. |
| `check_consistency(c.docs, build_world(seed))` | A bare `docs` dict carries no seed, so the pairing is **unverifiable** and emits a `UserWarning` every time — passing the wrong seed here is the classic silent-wrong hazard, so it warns loudly rather than returning a fabricated set. |
| `check_consistency(c.docs)` | Raises `ValueError` — no seed to derive a world from. |

After persisting `manifest.json` and reloading it, re-score safely by rebuilding the `Corpus`
(or by regenerating with `generate(manifest['seed'])`) and using the one-arg form, or by passing
the reloaded manifest alongside the corpus so both seeds are cross-checked:

```python
findings = check_consistency(c, reloaded_manifest)   # both seeds present → verified, no warning
```

## Flaw types (labeled)

- `contradiction` — a canonical figure in one doc disagrees with the world / other docs.
- `arithmetic_error` — the capital-account rollforward stops summing to the stated NAV.
- `ungrounded_claim` — an IC-memo metric with no support anywhere in the corpus.

Note the vocabulary split: `manifest["flaws"]` (the answer key, from `inject.py`) records this
type as `arithmetic_error`, while `check_consistency`/`detect_worldfree` findings (the detector
output, from `check.py`) name the same defect class `arithmetic` (matching the general
`contradiction`/`arithmetic` finding-type naming used throughout the checker). The two vocabularies
are intentionally not unified — renaming either would be a breaking change for integrators that
already key off one or the other — so a downstream tool comparing findings against the answer key
must map `arithmetic_error` (flaw type) <-> `arithmetic` (finding type) itself; see `eval/eval.py`'s
`_key()` for the reference mapping.

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

Clean corpus ties out (0 findings, 0 flaws, arithmetic ties, all 7 docs present) and injected flaws are
labeled AND detected at exactly their locations (`contradiction_labels_match_detections`) — checked
across a **201-seed range**, including 21 seeds with a negative `lp_allocated_gain` (a fund posting a
loss renders e.g. `"Allocated net gain: $-2,650,000"`), not just one hand-picked seed. Every canonical
figure (`management_fee`, `carried_interest`, `hurdle`, `fund_size`, `lp_commitment`, `distributions`,
`ending_nav`) has its own contradiction-detection round trip. Generation is reproducible (same
seed+injects → byte-identical docs + manifest).

### World-free detector vs a naive baseline (measured head-to-head)

`check_consistency(docs, world)` is a reference **oracle** — it is handed the world it grades against,
so passing it proves nothing about detection *difficulty*. To show the harness actually scores
detectors, two **world-free** detectors (they compare documents to EACH OTHER, never to world truth)
are scored against the labeled answer key on a corpus with three isolable contradictions + one
arithmetic break:

- `detect_naive(docs)` — competent-but-naive baseline: on any cross-doc disagreement, flag **every**
  document carrying that figure (the conflict is real, but the culprit can't be named).
- `detect_worldfree(docs)` — majority-vote to isolate the odd-one-out + re-derive the capital-account
  rollforward from its own lines.

| detector | precision | recall | F1 | TP | FP | FN |
|---|---|---|---|---|---|---|
| oracle (reads world) | 1.000 | 1.000 | 1.000 | 4 | 0 | 0 |
| **worldfree (no world)** | **1.000** | **1.000** | **1.000** | 4 | 0 | 0 |
| naive baseline | 0.364 | 1.000 | 0.533 | 4 | 7 | 0 |

Both detectors find every real flaw (recall 1.000), but the naive baseline over-flags 7 innocent
documents (precision 0.364) while the consensus detector isolates exactly the deviating doc
(precision 1.000) — a **measured precision gap of 0.636** — and reaches the *same* answer-key set as
the world-reading oracle without ever reading the world (`worldfree_matches_oracle`). [measured, one
seed 20260704; all figures printed by `eval/eval.py`.] Majority-vote isolation requires a figure to
appear in ≥3 documents; on a 2-doc disagreement `detect_worldfree` honestly falls back to flagging
both (no majority to arbitrate).

## Honest scope

One WM alternatives-diligence world; templated documents (not LLM-generated); figures consistent +
plausible but not full regulatory depth. The structural checker catches numeric contradictions +
arithmetic breaks; semantic/ungrounded flaws are *labeled* for a downstream red-team. Generalizes to
hedge-fund and VC worlds via new world states + renderers.

## Where it fits

A test-harness foundation for downstream tools that need labeled corpora with known answers to be
built and scored honestly — for example, a decision red-team, or a document-grounding defense for a
RAG system.

## License

MIT — see [LICENSE](LICENSE).
