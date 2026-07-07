"""Consistency checker: does the corpus tie out to the world state?

For each canonical labeled figure, extract its value from every document that
carries it and compare to the world truth -> a mismatch is a `contradiction`
finding. Separately, re-derive the capital-account rollforward from its own lines
and verify the equation -> a mismatch is an `arithmetic` finding.

This is what a clean corpus must pass (0 findings) and what makes injected flaws
detectable at exactly their labeled locations.
"""
from __future__ import annotations

import re
from collections import Counter

from .render import (
    LBL_MGMT_FEE, LBL_CARRY, LBL_HURDLE, LBL_FUND_SIZE, LBL_LP_COMMIT,
    LBL_DISTRIB, LBL_ENDING_NAV, LBL_CONTRIB, LBL_ALLOC_GAIN, LBL_ALLOC_FEES,
)

# field key -> (label, docs it appears in, world-truth accessor, kind)
_PCT = "pct"
_MONEY = "money"

FIELDS = {
    "management_fee": (LBL_MGMT_FEE, ["ppm", "lpa", "ddq", "adv"], lambda w: w.mgmt_fee_pct, _PCT),
    "carried_interest": (LBL_CARRY, ["ppm", "lpa", "ddq"], lambda w: w.carry_pct, _PCT),
    "hurdle": (LBL_HURDLE, ["ppm", "lpa"], lambda w: w.hurdle_pct, _PCT),
    "fund_size": (LBL_FUND_SIZE, ["ppm", "adv"], lambda w: w.committed_capital, _MONEY),
    "lp_commitment": (LBL_LP_COMMIT, ["lpa", "k1", "capital_account"], lambda w: w.lp_commitment, _MONEY),
    "distributions": (LBL_DISTRIB, ["k1", "capital_account"], lambda w: w.distributions, _MONEY),
    "ending_nav": (LBL_ENDING_NAV, ["k1", "capital_account"], lambda w: w.ending_nav, _MONEY),
}

_MONEY_RE = re.compile(r"\$\s*(-?[\d,]+(?:\.\d+)?)")
_PCT_RE = re.compile(r"([\d.]+)\s*%")


def _value_after_label(text: str, label: str, kind: str):
    for line in text.splitlines():
        s = line.strip()
        if s.startswith(label):
            rest = s[len(label):]
            m = (_MONEY_RE if kind == _MONEY else _PCT_RE).search(rest)
            if m:
                return float(m.group(1).replace(",", ""))
    return None


def check_consistency(docs: dict, world) -> list:
    findings = []

    # cross-document figure agreement vs world truth
    for key, (label, doc_names, truth_fn, kind) in FIELDS.items():
        truth = float(truth_fn(world))
        for name in doc_names:
            if name not in docs:
                continue
            got = _value_after_label(docs[name], label, kind)
            if got is None:
                continue
            if abs(got - truth) > 1e-6:
                findings.append({"type": "contradiction", "doc": name, "field": key,
                                 "found": got, "expected": truth})

    # capital-account rollforward arithmetic
    ca = docs.get("capital_account")
    if ca is not None:
        contrib = _value_after_label(ca, LBL_CONTRIB, _MONEY)
        gain = _value_after_label(ca, LBL_ALLOC_GAIN, _MONEY)
        fees = _value_after_label(ca, LBL_ALLOC_FEES, _MONEY)
        dist = _value_after_label(ca, LBL_DISTRIB, _MONEY)
        nav = _value_after_label(ca, LBL_ENDING_NAV, _MONEY)
        if None not in (contrib, gain, fees, dist, nav):
            computed = contrib + gain - fees - dist
            if abs(computed - nav) > 1e-6:
                findings.append({"type": "arithmetic", "doc": "capital_account", "field": "rollforward",
                                 "found": nav, "expected": computed})

    return findings


# ---------------------------------------------------------------------------------
# WORLD-FREE detectors (no ground-truth world; compare documents to EACH OTHER).
#
# check_consistency() above is a reference *oracle*: it is handed the world it grades
# against, so passing it proves nothing about detection difficulty. These detectors
# never read the world -- they are the objects a downstream tool actually has to be.
# ---------------------------------------------------------------------------------

def _collect_field_values(docs: dict) -> dict:
    """{field_key: {doc_name: value}} for every canonical figure present, world-free."""
    out = {}
    for key, (label, doc_names, _truth_fn, kind) in FIELDS.items():
        vals = {}
        for name in doc_names:
            if name not in docs:
                continue
            got = _value_after_label(docs[name], label, kind)
            if got is not None:
                vals[name] = got
        if vals:
            out[key] = vals
    return out


def _rollforward_finding(docs: dict) -> list:
    """Re-derive the capital-account rollforward from ITS OWN lines (world-free)."""
    findings = []
    ca = docs.get("capital_account")
    if ca is not None:
        contrib = _value_after_label(ca, LBL_CONTRIB, _MONEY)
        gain = _value_after_label(ca, LBL_ALLOC_GAIN, _MONEY)
        fees = _value_after_label(ca, LBL_ALLOC_FEES, _MONEY)
        dist = _value_after_label(ca, LBL_DISTRIB, _MONEY)
        nav = _value_after_label(ca, LBL_ENDING_NAV, _MONEY)
        if None not in (contrib, gain, fees, dist, nav):
            computed = contrib + gain - fees - dist
            if abs(computed - nav) > 1e-6:
                findings.append({"type": "arithmetic", "doc": "capital_account",
                                 "field": "rollforward", "found": nav, "expected": computed})
    return findings


def detect_naive(docs: dict) -> list:
    """Naive world-free baseline: what a competent engineer does with NO ground truth
    and no consensus reasoning -- when a labeled figure disagrees across documents,
    flag EVERY document that carries it (the conflict is real, but the culprit cannot
    be named). Plus the same self-contained rollforward check.
    """
    findings = []
    for key, vals in _collect_field_values(docs).items():
        if len({round(v, 6) for v in vals.values()}) > 1:      # any disagreement
            for name, v in vals.items():
                findings.append({"type": "contradiction", "doc": name, "field": key,
                                 "found": v})
    findings.extend(_rollforward_finding(docs))
    return findings


def detect_worldfree(docs: dict) -> list:
    """World-free consensus detector: for each labeled figure carried by multiple
    documents, take the MAJORITY value as the (unstated) consensus and flag only the
    documents that deviate from it -- isolating the odd-one-out without any world truth.
    Falls back to the naive flag-all behaviour when there is no clear majority (a tie or
    all-distinct set), which is honest: with 2 disagreeing docs you cannot tell which is
    wrong. Plus the self-contained rollforward check.
    """
    findings = []
    for key, vals in _collect_field_values(docs).items():
        rounded = {name: round(v, 6) for name, v in vals.items()}
        distinct = set(rounded.values())
        if len(distinct) <= 1:
            continue                                            # all agree -> clean
        counts = Counter(rounded.values()).most_common()
        top_val, top_n = counts[0]
        second_n = counts[1][1] if len(counts) > 1 else 0
        if top_n >= 2 and top_n > second_n:
            # clear majority -> flag only the deviating documents
            for name, v in vals.items():
                if rounded[name] != top_val:
                    findings.append({"type": "contradiction", "doc": name, "field": key,
                                     "found": v, "expected": top_val})
        else:
            # no majority to arbitrate -> honestly cannot isolate; flag all disagreeing
            for name, v in vals.items():
                findings.append({"type": "contradiction", "doc": name, "field": key,
                                 "found": v})
    findings.extend(_rollforward_finding(docs))
    return findings
