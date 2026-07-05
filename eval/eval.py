"""redteam-desk eval -- score the red-team against synth-corpus's labeled ground
truth across seeds. Exits 0 on thresholds.

    python eval/eval.py

Independent detectors vs an independently-generated answer key -> an honest score:
clean packets raise NO findings (no false positives); flawed packets catch every
planted flaw (recall 1.0) with no spurious findings (precision 1.0).
"""
import os
import sys

REDTEAM_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SYNTH = os.path.join(os.path.dirname(REDTEAM_ROOT), "synth-corpus")
sys.path.insert(0, REDTEAM_ROOT)
sys.path.insert(0, SYNTH)

from redteam.verify import (                       # noqa: E402
    run_redteam,
    detect_arithmetic,
    detect_contradictions,
)
from redteam.baseline import naive_verify          # noqa: E402
from synthfin.generate import generate            # noqa: E402

SEEDS = [20260704, 4242, 71]
_MAP = {"contradiction": "contradiction", "ungrounded_claim": "unsupported_claim", "arithmetic_error": "arithmetic"}
INJECTS = [
    {"type": "contradiction", "doc": "ddq", "field": "management_fee"},
    {"type": "ungrounded_claim"},
    {"type": "arithmetic_error"},
]


def main() -> int:
    checks = {}
    clean_false_positives = 0
    total_planted = 0
    total_hits = 0
    total_findings_flawed = 0

    for seed in SEEDS:
        # clean packet -> no findings
        clean = run_redteam(generate(seed))
        clean_false_positives += len(clean["findings"])

        # flawed packet -> catch every planted flaw
        corpus = generate(seed, injects=INJECTS)
        report = run_redteam(corpus)
        planted = corpus.manifest["flaws"]
        found = {(f["type"], f["doc"]) for f in report["findings"]}
        hits = sum(1 for p in planted if (_MAP[p["type"]], p["doc"]) in found)
        total_planted += len(planted)
        total_hits += hits
        total_findings_flawed += len(report["findings"])
        checks[f"seed_{seed}_verdict_high_risk"] = report["verdict"] == "high-risk"
        print(f"[seed {seed}] clean_findings={len(clean['findings'])} "
              f"recall={hits}/{len(planted)} findings={len(report['findings'])} verdict={report['verdict']}")

    # --- red/green regression cases for the two adversarial-review fixes ---
    # (1) FAIL-OPEN on negative money: a broken rollforward hidden behind a LOSS
    #     ($-5,000,000) must be caught -- and a CORRECT negative rollforward must not
    #     be flagged (proves negatives are parsed, not just always-flagged).
    neg_broken = {"capital_account": (
        "Contributions to date: $10,000,000\n"
        "Allocated net gain: $-5,000,000\n"          # a loss -- was parsed as None (fail-open)
        "Allocated management fees: $200,000\n"
        "Cumulative distributions: $1,000,000\n"
        "Ending capital account (NAV): $9,000,000\n"  # 3,800,000 != 9,000,000 -> should FAIL
    )}
    neg_clean = {"capital_account": (
        "Contributions to date: $10,000,000\n"
        "Allocated net gain: $-5,000,000\n"
        "Allocated management fees: $200,000\n"
        "Cumulative distributions: $1,000,000\n"
        "Ending capital account (NAV): $3,800,000\n"  # sums correctly -> no finding
    )}
    checks["redcase_neg_rollforward_caught"] = len(detect_arithmetic(neg_broken)) == 1
    checks["redcase_neg_rollforward_clean_ok"] = detect_arithmetic(neg_clean) == []

    # (2) CORRECTNESS on a 1-1 tie: a two-doc disagreement must NOT single out one
    #     (possibly correct) doc. ppm carries the WRONG value first (old modal), lpa
    #     the CORRECT one -- old code accused lpa alone; fix flags BOTH as unresolved.
    two_doc = {
        "ppm": "Preferred return (hurdle): 9.0%\n",   # wrong, inserted first
        "lpa": "Preferred return (hurdle): 8.0%\n",   # correct, was wrongly accused alone
    }
    tie = detect_contradictions(two_doc)
    checks["redcase_tie_flags_both_not_correct_doc"] = (
        {f["doc"] for f in tie} == {"ppm", "lpa"}
        and all("unresolved conflict" in f["detail"] for f in tie)
    )
    print(f"[redcase] neg_rollforward_caught={len(detect_arithmetic(neg_broken))} "
          f"neg_clean_findings={len(detect_arithmetic(neg_clean))} "
          f"tie_docs_flagged={sorted({f['doc'] for f in tie})}")

    recall = total_hits / total_planted if total_planted else 0.0
    precision = total_hits / total_findings_flawed if total_findings_flawed else 0.0
    checks["no_false_positives_on_clean"] = clean_false_positives == 0
    checks["recall_1.0"] = recall == 1.0
    checks["precision_1.0"] = precision == 1.0

    # --- MEASURED head-to-head vs a FAIR naive keyword/regex baseline ---------
    # Turns the README's asserted "out-of-the-box keyword verifiers are unreliable"
    # into owned evidence: run the naive incumbent over the SAME labeled packets and
    # measure the gap. The baseline is a reasonable first-cut (keyword-anchored
    # cross-doc consistency + performance-claim flagging), NOT a strawman -- it
    # simply lacks the domain-modeled rollforward reconstruction and the canonical
    # anchored parsing that make the deterministic detector reliable.
    b_planted = b_hits = b_findings_flawed = b_clean_fp = 0
    for seed in SEEDS:
        b_clean_fp += len(naive_verify(generate(seed))["findings"])
        corpus = generate(seed, injects=INJECTS)
        b_report = naive_verify(corpus)
        planted = corpus.manifest["flaws"]
        found = {(f["type"], f["doc"]) for f in b_report["findings"]}
        b_hits += sum(1 for p in planted if (_MAP[p["type"]], p["doc"]) in found)
        b_planted += len(planted)
        b_findings_flawed += len(b_report["findings"])
    b_recall = b_hits / b_planted if b_planted else 0.0
    b_precision = b_hits / b_findings_flawed if b_findings_flawed else 0.0
    # The deterministic detector must STRICTLY dominate the naive baseline on every
    # axis -- higher recall, higher precision, fewer false positives on clean packets.
    checks["baseline_recall_worse"] = recall > b_recall
    checks["baseline_precision_worse"] = precision > b_precision
    checks["baseline_more_clean_false_positives"] = clean_false_positives < b_clean_fp
    print("\n=== HEAD-TO-HEAD (measured, same seeds/packets) ===")
    print(f"deterministic : recall={recall:.3f} precision={precision:.3f} clean_FP={clean_false_positives}")
    print(f"naive baseline: recall={b_recall:.3f} precision={b_precision:.3f} clean_FP={b_clean_fp}")

    print("\n=== METRICS (measured) ===")
    for k, v in checks.items():
        print(f"{'OK  ' if v else 'FAIL'} {k}")
    print(f"recall={recall:.3f}  precision={precision:.3f}  clean_false_positives={clean_false_positives}")
    passed = all(checks.values())
    print("RESULT:", "PASS" if passed else "FAIL")
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
