# synth-corpus — synthetic financial corpus generator (labeled test-harness)

Generate realistic wealth-domain document sets **with a ground-truth answer key**. Every document
renders from one internally-consistent world state (so a fund's PPM ↔ LPA ↔ DDQ ↔ ADV ↔
capital-account ↔ K-1 ↔ IC memo all tie out), and a flaw-injection layer plants **labeled** defects
so any downstream tool can be scored against known truth. Deterministic + offline. For testing only.

## Quickstart

```
python eval/eval.py     # 23/23 checks, exit 0
python run_demo.py      # writes out/clean + out/flawed
```

Only dependency is numpy (seeded). Documents are templated markdown; the manifest is JSON.

## What it produces

A `Corpus{docs, manifest}` from `generate(seed, injects=[...])`:

- **docs** — `ppm, lpa, ddq, adv, k1, capital_account, ic_memo` (a WM alternatives-diligence world).
- **manifest** — the world state (source of truth) + the list of injected flaws (the answer key).

## Flaw types (labeled)

- `contradiction` — a canonical figure in one doc disagrees with the world / other docs.
- `arithmetic_error` — the capital-account rollforward stops summing to the stated NAV.
- `ungrounded_claim` — an IC-memo metric with no support anywhere in the corpus.

```python
from synthfin import generate, check_consistency, build_world
c = generate(20260704, injects=[
    {"type": "contradiction", "doc": "ddq", "field": "management_fee"},
    {"type": "arithmetic_error"},
    {"type": "ungrounded_claim"},
])
findings = check_consistency(c.docs, build_world(20260704))   # structural detections
answer_key = c.manifest["flaws"]                              # ground truth to score against
```

## Measured (eval.py, exit 0 — 23/23)

Clean corpus ties out (0 findings, 0 flaws, arithmetic ties, all 7 docs present); injected flaws are
labeled AND detected at exactly their locations (`contradiction_labels_match_detections`); generation
is reproducible (same seed+injects → byte-identical docs + manifest).

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

The test-harness foundation for the wealth-tech track (consilium, the decision red-team redteam-desk,
and the BD-APP graph-RAG defense) — it supplies labeled corpora with known answers so those tools can
be built and scored honestly.
