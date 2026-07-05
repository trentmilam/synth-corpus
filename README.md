# redteam-desk — an AI decision red-team (advisor second-opinion)

Before a high-stakes wealth recommendation is acted on, this adversarially reviews the decision
packet — the IC-memo recommendation plus its supporting data room — and surfaces integrity problems
a confident, fluent draft can hide: **cross-document contradictions**, **unsupported performance
claims**, and **arithmetic errors** — every finding **citation-gated** — then returns a **risk
verdict**. Built for the people who protect the wealthy: RIAs, family offices, fund ICs.

## Quickstart

```
python eval/eval.py    # scored vs labeled ground truth
python run_demo.py     # one worked decision packet
```

The eval imports the sibling `synth-corpus` generator to build **labeled** flawed decision packets,
then scores the red-team's *independent* detectors against that answer key.

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
| naive keyword baseline | 0.667 | 0.261 | 17 |

The naive baseline fails in two honest ways: it **misses the arithmetic break entirely** (a keyword
scanner has no capital-account rollforward model — the exact domain modeling this tool adds), and it
**false-positives** by keyword-substring collision (`management fee` matching the *"allocated management
fees $225,000"* line) and by over-flagging legitimate MOIC/TVPI/DPI performance lines it cannot tell
apart from an unbacked IRR claim. The gap is asserted by the eval, not just printed.

## How it works

Follows the validated FinGround-style blueprint — atomic claims → verdict {supported / contradicted /
unverifiable} + formula reconstruction — implemented as three **deterministic** detectors
(`redteam/verify.py`):

- **contradiction** — the same labeled figure carries different values across documents (docs disagree
  with *each other*; the minority doc is flagged);
- **unsupported_claim** — a rate-of-return (IRR / annualized return) assertion the alternatives data
  room cannot substantiate (no dated cash flows);
- **arithmetic** — the capital-account rollforward is re-derived and must sum to the stated NAV.

`run_redteam(corpus) -> {verdict, findings[]}`; verdict is `high-risk` (a contradiction or arithmetic
error), `caution` (an unsupported claim), or `proceed`.

## Why deterministic (grounded in the deep-research pass)

The research pass (105 agents; see `docs/superpowers/specs/2026-07-04-redteam-desk-design.md`) found
the pattern validated in an adjacent regulated domain (a critic layer cut hallucination 11.3%→3.8%),
no equivalent product for wealth managers (white space), and — critically — that **out-of-the-box
LLMs are unreliable citation verifiers**. So v1 is deterministic over authoritative documents, not an
LLM-as-judge; the v2 upgrade is a task-specific fine-tuned verifier, still authoritative-corpus-first.

## Honest scope (v1)

Deterministic detectors on the synth-corpus document schema; the unsupported-claim detector targets
return-rate assertions specifically (general ungrounded-claim detection needs NLI — v2). Citations are
document+line references. Not investment/legal advice; a decision aid, not a decision maker (aligns
with FINRA Rule 3110 supervision — a human stays in the loop).

## Where it fits

The capstone of the wealth-tech track: it consumes `` labeled packets and is
scored against their ground truth, and it reuses the integrity philosophy of ``
(citation-gating) and `` (BD-APP conflict thinking).
