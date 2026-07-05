"""synth-corpus eval -- proves the harness is trustworthy. Exits 0 on all checks.

    python eval/eval.py

Deterministic. Asserts: clean corpus ties out (0 findings, 0 flaws); injected flaws
are labeled AND detected at exactly their locations (the answer key is correct);
arithmetic ties clean and breaks when injected; generation is reproducible.
"""
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from synthfin.generate import generate            # noqa: E402
from synthfin.check import (                        # noqa: E402
    check_consistency, detect_worldfree, detect_naive,
)
from synthfin.world import build_world             # noqa: E402

SEED = 20260704


# --- scoring: match detector findings to the labeled answer key -----------------
# The gold set is the CHECKER-VISIBLE flaw types (numeric contradictions + arithmetic
# breaks). Ungrounded claims are excluded: no world-free numeric detector can know a
# lone, uncorroborated claim is false, so scoring on it would be unfair to BOTH
# detectors. Arithmetic is matched at (type, doc) granularity because the answer key
# records the mutated INPUT field (allocated_net_gain) while a detector can only name
# the equation (rollforward); contradictions are matched at (type, doc, field).
_VISIBLE = {"contradiction", "arithmetic", "arithmetic_error"}


def _key(item: dict):
    typ = item["type"]
    if typ in ("arithmetic", "arithmetic_error"):
        return ("arithmetic", item["doc"])
    if typ == "contradiction":
        return ("contradiction", item["doc"], item["field"])
    return (typ, item.get("doc"), item.get("field"))


def _prf(findings: list, flaws: list) -> dict:
    gold = {_key(f) for f in flaws if f["type"] in _VISIBLE}
    got = {_key(g) for g in findings if g["type"] in _VISIBLE}
    tp = len(got & gold)
    fp = len(got - gold)
    fn = len(gold - got)
    prec = tp / (tp + fp) if (tp + fp) else 1.0
    rec = tp / (tp + fn) if (tp + fn) else 1.0
    f1 = 2 * prec * rec / (prec + rec) if (prec + rec) else 0.0
    return {"tp": tp, "fp": fp, "fn": fn, "precision": prec, "recall": rec, "f1": f1,
            "keys": got}


def main() -> int:
    world = build_world(SEED)
    checks = {}

    # --- clean corpus ---
    clean = generate(SEED)
    clean_findings = check_consistency(clean.docs, world)
    checks["cross_doc_consistency"] = len(clean_findings) == 0
    checks["no_false_flaws"] = clean.manifest["flaws"] == []
    checks["arithmetic_correct_clean"] = not any(f["type"] == "arithmetic" for f in clean_findings)
    checks["all_docs_present"] = set(clean.docs) == {"ppm", "lpa", "ddq", "adv", "k1", "capital_account", "ic_memo"}

    # --- flawed corpus ---
    injects = [
        {"type": "contradiction", "doc": "ddq", "field": "management_fee"},
        {"type": "ungrounded_claim"},
        {"type": "arithmetic_error"},
    ]
    flawed = generate(SEED, injects=injects)
    flaws = flawed.manifest["flaws"]
    findings = check_consistency(flawed.docs, world)

    checks["injection_count"] = len(flaws) == 3
    checks["flaws_well_formed"] = all({"type", "doc", "field", "truth", "injected"} <= set(f) for f in flaws)
    checks["detect_contradiction"] = any(
        f["type"] == "contradiction" and f["doc"] == "ddq" and f["field"] == "management_fee" for f in findings)
    checks["detect_arithmetic"] = any(f["type"] == "arithmetic" and f["doc"] == "capital_account" for f in findings)
    checks["ungrounded_labeled"] = any(f["type"] == "ungrounded_claim" for f in flaws)

    # labels == detections for the structural (checker-visible) flaw types: no spurious, no missed
    inj_contra = {(f["doc"], f["field"]) for f in flaws if f["type"] == "contradiction"}
    found_contra = {(f["doc"], f["field"]) for f in findings if f["type"] == "contradiction"}
    checks["contradiction_labels_match_detections"] = inj_contra == found_contra

    # --- answer-key integrity: no-op injects must be REJECTED, not recorded as flaws ---
    # (red-cases: each of these previously recorded a ground-truth flaw for a defect that
    #  is not actually present in the corpus; each must now raise.)
    def _rejected(inj) -> bool:
        try:
            generate(SEED, injects=[inj])
        except ValueError:
            return True
        return False

    # (a) contradiction targeting a doc that carries no such label -> nothing changes
    checks["reject_contradiction_missing_label"] = _rejected(
        {"type": "contradiction", "doc": "k1", "field": "management_fee"})
    # (b) contradiction whose injected value EQUALS the world truth -> contradicts nothing
    checks["reject_contradiction_equals_truth"] = _rejected(
        {"type": "contradiction", "doc": "ddq", "field": "management_fee", "value": world.mgmt_fee_pct})
    # (c) arithmetic_error with delta=0 -> the rollforward still sums to NAV
    checks["reject_arithmetic_zero_delta"] = _rejected({"type": "arithmetic_error", "delta": 0})

    # green: a valid contradiction on the SAME field/doc still records + is detectable (fix is not over-broad)
    valid = generate(SEED, injects=[{"type": "contradiction", "doc": "ddq", "field": "management_fee"}])
    valid_findings = check_consistency(valid.docs, world)
    checks["valid_contradiction_still_records"] = len(valid.manifest["flaws"]) == 1
    # every recorded flaw of a checker-visible type is REAL (detected at its labeled location)
    checks["every_recorded_flaw_is_detectable"] = all(
        any(g["type"] == "contradiction" and g["doc"] == f["doc"] and g["field"] == f["field"]
            for g in valid_findings)
        for f in valid.manifest["flaws"] if f["type"] == "contradiction")

    # --- MEASURED head-to-head: world-free detector vs a naive baseline ---------
    # The point of the harness is to SCORE detectors that do NOT get to read the
    # world (check_consistency is a reference oracle: it is handed `world`, so passing
    # it proves nothing about detection difficulty). Here we plant contradictions on
    # three fields that each appear in >=3 docs (so a majority exists to isolate the
    # odd-one-out) plus one arithmetic break, then score two WORLD-FREE detectors
    # against the labeled answer key:
    #   * detect_naive     -- competent-but-naive: on any cross-doc disagreement, flag
    #                         EVERY doc carrying that figure (cannot name the culprit).
    #   * detect_worldfree -- majority-vote to isolate the deviating doc + re-derive the
    #                         rollforward from its own lines. No world truth is read.
    ab_injects = [
        {"type": "contradiction", "doc": "ddq", "field": "management_fee"},   # in ppm,lpa,ddq,adv
        {"type": "contradiction", "doc": "ppm", "field": "carried_interest"}, # in ppm,lpa,ddq
        {"type": "contradiction", "doc": "k1", "field": "lp_commitment"},     # in lpa,k1,capital_account
        {"type": "arithmetic_error"},
    ]
    ab = generate(SEED, injects=ab_injects)
    ab_flaws = ab.manifest["flaws"]

    oracle_find = check_consistency(ab.docs, world)     # reads world (reference oracle)
    wf_find = detect_worldfree(ab.docs)                 # world-free
    naive_find = detect_naive(ab.docs)                  # world-free, naive baseline

    oracle = _prf(oracle_find, ab_flaws)
    wf = _prf(wf_find, ab_flaws)
    naive = _prf(naive_find, ab_flaws)

    # world-free detector reaches the answer key exactly...
    checks["worldfree_precision_perfect"] = wf["precision"] == 1.0
    checks["worldfree_recall_perfect"] = wf["recall"] == 1.0
    # ...and matches the world-reading oracle without ever reading the world
    checks["worldfree_matches_oracle"] = wf["keys"] == oracle["keys"]
    # the naive baseline finds every real flaw too (fair: it is NOT crippled on recall)
    checks["naive_recall_equal"] = naive["recall"] == wf["recall"] == 1.0
    # ...but over-flags innocent docs, so its precision is measurably worse (the wedge)
    checks["naive_overflags"] = naive["fp"] > 0 and wf["fp"] == 0
    checks["worldfree_beats_naive_precision"] = wf["precision"] > naive["precision"]

    print("\n=== MEASURED head-to-head (world-free detectors vs labeled answer key) ===")
    print(f"{'detector':<22}{'P':>8}{'R':>8}{'F1':>8}{'TP':>5}{'FP':>5}{'FN':>5}")
    for nm, m in (("oracle (reads world)", oracle), ("worldfree (no world)", wf),
                  ("naive baseline", naive)):
        print(f"{nm:<22}{m['precision']:>8.3f}{m['recall']:>8.3f}{m['f1']:>8.3f}"
              f"{m['tp']:>5}{m['fp']:>5}{m['fn']:>5}")
    print(f"MEASURED precision gap (worldfree - naive): "
          f"{wf['precision'] - naive['precision']:.3f}")

    # --- determinism ---
    a = generate(SEED, injects=injects)
    b = generate(SEED, injects=injects)
    checks["determinism_docs"] = a.docs == b.docs
    checks["determinism_manifest"] = json.dumps(a.manifest, sort_keys=True) == json.dumps(b.manifest, sort_keys=True)

    print("=== synth-corpus checks (measured) ===")
    for k, v in checks.items():
        print(f"{'OK  ' if v else 'FAIL'} {k}")
    print(f"\ninjected flaws: {[f['type'] for f in flaws]}")
    print(f"checker findings: {[(f['type'], f['doc']) for f in findings]}")
    passed = all(checks.values())
    print("RESULT:", "PASS" if passed else "FAIL")
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
