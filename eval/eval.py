"""synth-corpus eval -- proves the harness is trustworthy. Exits 0 on all checks.

    python eval/eval.py

Deterministic. Asserts: clean corpus ties out (0 findings, 0 flaws); injected flaws
are labeled AND detected at exactly their locations (the answer key is correct);
arithmetic ties clean and breaks when injected; generation is reproducible.

Clean-corpus and injected-flaw-detection checks run across a SEED_RANGE (not one
hardcoded seed): a single lucky seed previously hid a money-parsing regex bug that
silently dropped every negative-valued figure (a fund posting a loss renders
"Allocated net gain: $-2,650,000"), so the range explicitly includes seeds known to
produce a negative `lp_allocated_gain` (see SEED_RANGE below).
"""
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from synthfin.generate import generate            # noqa: E402
from synthfin.check import (                        # noqa: E402
    check_consistency, detect_worldfree, detect_naive, FIELDS,
    _value_after_label, _MONEY, LBL_ALLOC_GAIN,
)
from synthfin.world import build_world             # noqa: E402

SEED = 20260704  # primary seed for the demo output, no-op-rejection tests, and the
                  # measured head-to-head (unaffected by seed choice -- see SEED_RANGE)

# Regression coverage: 1..200 plus seed 243 (both independently confirmed to produce a
# negative lp_allocated_gain -- a fund posting a loss). 20 of these 201 seeds are
# negative-gain (~10%, consistent with the ~8% measured across a larger sweep).
SEED_RANGE = sorted(set(range(1, 201)) | {243})


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
    checks = {}

    # --- clean-corpus + injected-flaw-detection checks, across SEED_RANGE ----------
    # Each check below is True only if it holds for EVERY seed in the range.
    neg_gain_seeds = [s for s in SEED_RANGE if build_world(s).lp_allocated_gain < 0]

    cross_doc_consistency_all = True
    no_false_flaws_all = True
    arithmetic_correct_clean_all = True
    all_docs_present_all = True
    injection_count_all = True
    flaws_well_formed_all = True
    detect_contradiction_all = True
    detect_arithmetic_all = True
    ungrounded_labeled_all = True
    contradiction_labels_match_all = True

    base_injects = [
        {"type": "contradiction", "doc": "ddq", "field": "management_fee"},
        {"type": "ungrounded_claim"},
        {"type": "arithmetic_error"},
    ]

    for s in SEED_RANGE:
        world_s = build_world(s)

        clean_s = generate(s)
        clean_findings_s = check_consistency(clean_s.docs, world_s)
        cross_doc_consistency_all &= len(clean_findings_s) == 0
        no_false_flaws_all &= clean_s.manifest["flaws"] == []
        arithmetic_correct_clean_all &= not any(f["type"] == "arithmetic" for f in clean_findings_s)
        all_docs_present_all &= set(clean_s.docs) == {
            "ppm", "lpa", "ddq", "adv", "k1", "capital_account", "ic_memo"}

        flawed_s = generate(s, injects=base_injects)
        flaws_s = flawed_s.manifest["flaws"]
        findings_s = check_consistency(flawed_s.docs, world_s)

        injection_count_all &= len(flaws_s) == 3
        flaws_well_formed_all &= all(
            {"type", "doc", "field", "truth", "injected"} <= set(f) for f in flaws_s)
        detect_contradiction_all &= any(
            f["type"] == "contradiction" and f["doc"] == "ddq" and f["field"] == "management_fee"
            for f in findings_s)
        detect_arithmetic_all &= any(
            f["type"] == "arithmetic" and f["doc"] == "capital_account" for f in findings_s)
        ungrounded_labeled_all &= any(f["type"] == "ungrounded_claim" for f in flaws_s)

        inj_contra_s = {(f["doc"], f["field"]) for f in flaws_s if f["type"] == "contradiction"}
        found_contra_s = {(f["doc"], f["field"]) for f in findings_s if f["type"] == "contradiction"}
        contradiction_labels_match_all &= inj_contra_s == found_contra_s

    checks["cross_doc_consistency"] = cross_doc_consistency_all
    checks["no_false_flaws"] = no_false_flaws_all
    checks["arithmetic_correct_clean"] = arithmetic_correct_clean_all
    checks["all_docs_present"] = all_docs_present_all
    checks["injection_count"] = injection_count_all
    checks["flaws_well_formed"] = flaws_well_formed_all
    checks["detect_contradiction"] = detect_contradiction_all
    checks["detect_arithmetic"] = detect_arithmetic_all
    checks["ungrounded_labeled"] = ungrounded_labeled_all
    checks["contradiction_labels_match_detections"] = contradiction_labels_match_all

    assert neg_gain_seeds, "SEED_RANGE must include at least one negative lp_allocated_gain seed"
    print(f"seed-range regression coverage: {len(SEED_RANGE)} seeds "
          f"({SEED_RANGE[0]}..{SEED_RANGE[-1]}), including {len(neg_gain_seeds)} with a "
          f"NEGATIVE lp_allocated_gain (e.g. seed {neg_gain_seeds[0]}) -- the exact class "
          f"of seed that a prior money-regex bug silently mishandled.")

    # --- Money-regex negative-value regression, made explicit and self-enforcing ---
    # (1) the money regex must PARSE a negative rendered figure, not silently return
    #     None, for every negative-gain seed in the range.
    checks["money_regex_parses_negative_values"] = all(
        _value_after_label(generate(s).docs["capital_account"], LBL_ALLOC_GAIN, _MONEY)
        == build_world(s).lp_allocated_gain
        for s in neg_gain_seeds)
    # (2) direct repro of the originally-reported bug: seed=4, truth=-600000, an
    #     arithmetic_error whose rendered result STAYS negative ($-100,000) -- before
    #     the fix this was silently skipped (empty findings); now it must be caught.
    neg_world = build_world(4)
    neg_flawed = generate(4, injects=[{"type": "arithmetic_error", "delta": 500_000}])
    neg_findings = check_consistency(neg_flawed.docs, neg_world)
    checks["detect_arithmetic_negative_rendered_value"] = any(
        f["type"] == "arithmetic" and f["doc"] == "capital_account" for f in neg_findings)

    # --- single-seed (SEED) checks below: no-op rejection, head-to-head, determinism ---
    world = build_world(SEED)

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
    # (d) unknown inject type -> nothing recognized to apply
    checks["reject_unknown_inject_type"] = _rejected({"type": "not_a_real_type"})
    # (e) empty ungrounded_claim text -> plants nothing
    checks["reject_empty_ungrounded_claim"] = _rejected({"type": "ungrounded_claim", "text": ""})

    # green: a valid contradiction on the SAME field/doc still records + is detectable (fix is not over-broad)
    valid = generate(SEED, injects=[{"type": "contradiction", "doc": "ddq", "field": "management_fee"}])
    valid_findings = check_consistency(valid.docs, world)
    checks["valid_contradiction_still_records"] = len(valid.manifest["flaws"]) == 1
    # every recorded flaw of a checker-visible type is REAL (detected at its labeled location)
    checks["every_recorded_flaw_is_detectable"] = all(
        any(g["type"] == "contradiction" and g["doc"] == f["doc"] and g["field"] == f["field"]
            for g in valid_findings)
        for f in valid.manifest["flaws"] if f["type"] == "contradiction")

    # --- Contradiction round-trip coverage for the remaining FIELDS ---------------
    # management_fee/carried_interest/lp_commitment are already exercised above/below;
    # the other 4 canonical figures need their own inject+detect round trip.
    for field_key, target_doc in (
        ("fund_size", "ppm"), ("hurdle", "ppm"),
        ("distributions", "k1"), ("ending_nav", "k1"),
    ):
        assert field_key in FIELDS, f"FIELDS is missing {field_key!r}"
        rt = generate(SEED, injects=[{"type": "contradiction", "doc": target_doc, "field": field_key}])
        rt_findings = check_consistency(rt.docs, world)
        checks[f"detect_contradiction_{field_key}"] = any(
            f["type"] == "contradiction" and f["doc"] == target_doc and f["field"] == field_key
            for f in rt_findings)

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
    a = generate(SEED, injects=base_injects)
    b = generate(SEED, injects=base_injects)
    checks["determinism_docs"] = a.docs == b.docs
    checks["determinism_manifest"] = json.dumps(a.manifest, sort_keys=True) == json.dumps(b.manifest, sort_keys=True)

    demo_flaws = a.manifest["flaws"]
    demo_findings = check_consistency(a.docs, world)

    print("=== synth-corpus checks (measured) ===")
    for k, v in checks.items():
        print(f"{'OK  ' if v else 'FAIL'} {k}")
    n = len(checks)
    n_pass = sum(1 for v in checks.values() if v)
    print(f"\ninjected flaws (seed {SEED}): {[f['type'] for f in demo_flaws]}")
    print(f"checker findings (seed {SEED}): {[(f['type'], f['doc']) for f in demo_findings]}")
    passed = all(checks.values())
    print(f"RESULT: {'PASS' if passed else 'FAIL'} ({n_pass}/{n} checks)")
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
