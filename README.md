# redteam-desk: checks an AI-generated investment recommendation before anyone acts on it

[![eval](https://github.com/trentmilam/redteam-desk/actions/workflows/eval.yml/badge.svg)](https://github.com/trentmilam/redteam-desk/actions/workflows/eval.yml)

Before anyone acts on a wealth recommendation, this checks it against the documents behind it. It
looks for three kinds of problems: figures that contradict each other across documents,
performance claims the data doesn't actually support, and arithmetic that doesn't reconcile. If it
can't verify the numbers, it says so instead of quietly signing off.

It works as a red-team pass (an adversarial review that assumes the recommendation could be wrong,
rather than trusting it by default) over the decision packet: the recommendation memo (the "IC
memo") plus its supporting documents (the "data room"). Every finding is citation-gated, meaning it
points back to the specific document and line it came from rather than resting on an unverified
claim, and the tool returns a risk verdict. Built for the people who protect the wealthy: RIAs,
family offices, fund ICs.

## Quickstart

Zero dependencies: just this repo and the Python standard library.

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

`redteam/` (the package this repo ships) is pure standard library, with no required dependencies.
Requires Python 3.9+ (developed on 3.12, see `.python-version`).

## Input schema

`run_redteam(docs)` takes a `dict[str, str]` mapping a document name to its raw text. Canonical
document names: `ppm`, `lpa`, `ddq`, `adv`, `k1`, `capital_account`, `ic_memo` (not all required;
see below). Full schema and per-check requirements are documented in `redteam/verify.py`'s module
docstring; in short:

- Contradictions are found by scanning every document for lines starting with one of the
  canonical labels in `redteam.verify.LABELS` (exact strings, e.g. `"Management fee:"`). A
  contradiction fires when the same label carries different values in ≥2 documents.
- Arithmetic reconstructs the capital-account rollforward from `docs["capital_account"]`,
  which must contain all five labels in `redteam.verify.CAPITAL_ACCOUNT_LABELS`, each starting its
  own line, verbatim. A reworded label is not recognized.
- Verdict is `high-risk` (a contradiction or arithmetic break), `caution` (only an unsupported
  claim), `insufficient-data` (nothing was found wrong, but the capital-account rollforward could
  not be verified because a required label was missing or unmatched), or `proceed` (checked, and
  it's clean). `insufficient-data` is deliberately distinct from `proceed`: "nothing was checked"
  must never render identically to "checked, and it's fine."
- Coverage: `run_redteam`'s `coverage` field also reports `labels_located` (which of
  `LABELS` were found, and in which documents) and `labels_not_located` (labels found in none of
  the documents). Check these before trusting a `proceed` verdict. A figure phrased so
  differently that no canonical label matches it at all won't appear in `labels_located`, and its
  cross-document contradiction check silently never ran for that figure. The verdict alone won't
  tell you that.

## Full reproduction (requires the companion synth-corpus repo)

The Quickstart above needs nothing beyond this repo. The measured recall and precision numbers
below, and the worked demo, additionally use a companion project, [`synth-corpus`][synth-corpus],
to generate labeled decision packets with planted, known flaws. That keeps the score honest: the
answer key and the detectors are independent code, not a checker grading itself.

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

Across 3 seeds, on packets with a planted fee contradiction, an unsupported IRR claim, and an
arithmetic break: recall 1.000, precision 1.000, zero false positives on clean packets; verdict
`high-risk` on every flawed packet. Because the generator (the answer key) and the detectors are
independent code, the score is honest, not a checker grading itself.

### Head-to-head vs a naive baseline (measured, same packets)

The claim that out-of-the-box keyword verifiers are unreliable for this task is backed by a direct
comparison. `eval.py` runs a fair naive incumbent (`redteam/baseline.py`: a single-pass
keyword/regex verifier that does keyword-anchored cross-document number consistency plus
performance-claim flagging, a reasonable first cut, not a strawman) over the same labeled packets
and scores it head-to-head:

| verifier | recall | precision | false positives on clean packets |
|---|---|---|---|
| deterministic (this tool) | 1.000 | 1.000 | 0 |
| naive keyword baseline | 0.667 | 0.240 | 19 |

The naive baseline fails in two ways. It misses the arithmetic break entirely, because a keyword
scanner has no model of the capital-account rollforward, which is exactly the domain modeling this
tool adds. And it produces false positives, both by keyword-substring collision (`management fee`
matching the "allocated management fees $225,000" line) and by over-flagging legitimate MOIC,
TVPI, and DPI performance lines it can't tell apart from an unbacked IRR claim. `eval.py` computes
this gap directly; it isn't just asserted in prose.

## How it works

Each claim resolves to a verdict (supported, contradicted, or unverifiable), with a reconstructed
formula where applicable. This is implemented as three deterministic detectors
(`redteam/verify.py`):

- `contradiction`: the same labeled figure carries different values across documents. Documents
  disagree with each other, and the minority doc is flagged.
- `unsupported_claim`: a rate-of-return (IRR or annualized return) assertion the alternatives data
  room cannot substantiate (no dated cash flows).
- `arithmetic`: the capital-account rollforward is re-derived and must sum to the stated NAV.

`run_redteam(docs) -> {verdict, findings[], coverage}`; see [Input schema](#input-schema) above for
verdict semantics.

## Why deterministic

Critic and verifier layers have shown real hallucination reductions in adjacent regulated domains,
but out-of-the-box LLMs are unreliable citation verifiers. So v1 here is deterministic over
authoritative documents, not an LLM acting as judge. The planned v2 upgrade is a task-specific
fine-tuned verifier, still grounded in the authoritative document corpus first.

## Honest scope (v1)

This uses deterministic detectors on the synth-corpus document schema; the unsupported-claim
detector targets return-rate assertions specifically. General ungrounded-claim detection needs NLI
(natural-language inference) and is planned for v2. Citations are document and line references.
This isn't investment or legal advice; it's a decision aid, not a decision maker, and a human
stays in the loop (consistent with FINRA Rule 3110 supervision).

## Where it fits

This tool consumes decision packets: either your own, in the `docs` dict shape described above, or
the labeled packets generated by the companion [`synth-corpus`][synth-corpus] project. When
reproducing the measured numbers above, it's scored against synth-corpus's ground truth. It
applies the same citation-gating discipline throughout: every finding ties to a document and line
reference, never an LLM's unverified say-so.

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md). Changes are tracked in [CHANGELOG.md](CHANGELOG.md).
