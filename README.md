# redteam-desk — an AI decision red-team (advisor second-opinion)

[![eval](https://github.com/trentmilam/redteam-desk/actions/workflows/eval.yml/badge.svg)](https://github.com/trentmilam/redteam-desk/actions/workflows/eval.yml)

Before a high-stakes wealth recommendation is acted on, this adversarially reviews the decision
packet — the IC-memo recommendation plus its supporting data room — and surfaces integrity problems
a confident, fluent draft can hide: **cross-document contradictions**, **unsupported performance
claims**, and **arithmetic errors** — every finding **citation-gated** — then returns a **risk
verdict**. Built for the people who protect the wealthy: RIAs, family offices, fund ICs.

## Quickstart

Zero dependencies — just this repo and the Python standard library:

```python
from redteam.verify import run_redteam

docs = {
    "ppm": "Total commitments (fund size): $500,000,000\n",
    "ddq": "Total commitments (fund size): $450,000,000\n",  # deliberate contradiction
}
report = run_redteam(docs)
print(report["verdict"])     # 'high-risk' -- the two documents disagree
print(report["findings"])    # each finding carries a `citation` back to the offending doc
```

Run it: `python -c "from redteam.verify import run_redteam; print(run_redteam({'ppm': 'Total commitments (fund size): \$500,000,000', 'ddq': 'Total commitments (fund size): \$450,000,000'}))"`

## Install

```
pip install .            # or: pip install -e . for local development
```

`redteam/` (the package this repo ships) is pure standard library — no required dependencies.
Requires Python 3.9+ (developed on 3.12, see `.python-version`).

## Input schema

`run_redteam(docs)` takes a `dict[str, str]` mapping a document name to its raw text. Canonical
document names: `ppm`, `lpa`, `ddq`, `adv`, `k1`, `capital_account`, `ic_memo` (not all required —
see below). Full schema and per-check requirements are documented in `redteam/verify.py`'s module
docstring; in short:

- **Contradictions** are found by scanning every document for lines starting with one of the
  canonical labels in `redteam.verify.LABELS` (exact strings, e.g. `"Management fee:"`) — a
  contradiction fires when the same label carries different values in ≥2 documents.
- **Arithmetic** reconstructs the capital-account rollforward from `docs["capital_account"]`,
  which must contain all five labels in `redteam.verify.CAPITAL_ACCOUNT_LABELS`, each starting its
  own line, verbatim — a reworded label is not recognized.
- **Verdict** is `high-risk` (a contradiction or arithmetic break), `caution` (only an unsupported
  claim), `insufficient-data` (nothing was found wrong, but the capital-account rollforward could
  not be verified — a required label was missing or unmatched), or `proceed` (checked, and it's
  clean). `insufficient-data` is deliberately distinct from `proceed`: "nothing was checked" must
  never render identically to "checked, and it's fine."
- **Coverage** — `run_redteam`'s `coverage` field also reports `labels_located` (which of
  `LABELS` were found, and in which documents) and `labels_not_located` (labels found in none of
  the documents). **Check these before trusting a `proceed` verdict**: a figure phrased so
  differently that no canonical label matches it at all won't appear in `labels_located`, and its
  cross-document contradiction check silently never ran for that figure — the verdict alone won't
  tell you that.

## Full reproduction (requires the companion synth-corpus repo)

The Quickstart above needs nothing beyond this repo. The measured recall/precision numbers below,
and the worked demo, additionally use a companion project, [`synth-corpus`][synth-corpus], to
generate **labeled** decision packets with planted, known flaws — so the score is honest (the
answer key and the detectors are independent code, not a checker grading itself).

[synth-corpus]: https://github.com/trentmilam/synth-corpus

```
git clone https://github.com/trentmilam/redteam-desk
# pinned to the synth-corpus release the numbers below were captured against;
# bump this alongside the numbers whenever synth-corpus cuts a new release
git clone --branch v0.1.0 https://github.com/trentmilam/synth-corpus
# the two repos must sit as siblings:
#   some-dir/redteam-desk
#   some-dir/synth-corpus
cd redteam-desk
pip install numpy          # synth-corpus's only dependency
python run_demo.py         # one worked decision packet
python eval/eval.py        # scored vs labeled ground truth
```

If `synth-corpus` isn't present at `../synth-corpus`, both scripts raise a clear
`RuntimeError` telling you to clone it, instead of a raw traceback.

## Measured (eval.py, exit 0)

Across 3 seeds, on packets with a planted fee-contradiction + unsupported-IRR claim + arithmetic
break: **recall 1.000, precision 1.000, zero false positives on clean packets**; verdict HIGH-RISK on
every flawed packet. Because the generator (answer key) and the detectors are independent code, the
score is honest — not a checker grading itself.

### Head-to-head vs a naive baseline (measured, same packets)

The claim below — that out-of-the-box keyword verifiers are unreliable for this task — is not left
asserted. `eval.py` runs a **fair naive incumbent** (`redteam/baseline.py`: a single-pass keyword/regex
verifier that does keyword-anchored cross-document number consistency + performance-claim flagging — a
reasonable first cut, not a strawman) over the *same* labeled packets and scores it head-to-head:

| verifier | recall | precision | false positives on clean packets |
|---|---|---|---|
| deterministic (this tool) | **1.000** | **1.000** | **0** |
| naive keyword baseline | 0.667 | 0.240 | 19 |

The naive baseline fails in two honest ways: it **misses the arithmetic break entirely** (a keyword
scanner has no capital-account rollforward model — the exact domain modeling this tool adds), and it
**false-positives** by keyword-substring collision (`management fee` matching the *"allocated management
fees $225,000"* line) and by over-flagging legitimate MOIC/TVPI/DPI performance lines it cannot tell
apart from an unbacked IRR claim. The gap is asserted by the eval, not just printed.

## How it works

Each claim resolves to a verdict — supported / contradicted / unverifiable — with a reconstructed
formula where applicable, implemented as three **deterministic** detectors (`redteam/verify.py`):

- **contradiction** — the same labeled figure carries different values across documents (docs disagree
  with *each other*; the minority doc is flagged);
- **unsupported_claim** — a rate-of-return (IRR / annualized return) assertion the alternatives data
  room cannot substantiate (no dated cash flows);
- **arithmetic** — the capital-account rollforward is re-derived and must sum to the stated NAV.

`run_redteam(docs) -> {verdict, findings[], coverage}`; see [Input schema](#input-schema) above for
verdict semantics.

## Why deterministic

Critic/verifier layers have shown meaningful hallucination reductions in adjacent regulated
domains, and — critically — **out-of-the-box LLMs are unreliable citation verifiers**. So v1 is
deterministic over authoritative documents, not an LLM-as-judge; the v2 upgrade is a
task-specific fine-tuned verifier, still authoritative-corpus-first.

## Honest scope (v1)

Deterministic detectors on the synth-corpus document schema; the unsupported-claim detector targets
return-rate assertions specifically (general ungrounded-claim detection needs NLI — v2). Citations are
document+line references. Not investment/legal advice; a decision aid, not a decision maker (aligns
with FINRA Rule 3110 supervision — a human stays in the loop).

## Where it fits

This tool consumes decision packets — either your own, in the `docs` dict shape described above, or
the labeled packets generated by the companion [`synth-corpus`][synth-corpus] project — and is scored
against synth-corpus's ground truth when reproducing the measured numbers above. It applies the same
citation-gating discipline throughout: every finding ties to a document+line reference, never an
LLM's unverified say-so.

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md). Changes are tracked in [CHANGELOG.md](CHANGELOG.md).
