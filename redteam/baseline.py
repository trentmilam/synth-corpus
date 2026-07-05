"""A NAIVE keyword/regex citation verifier -- the incumbent baseline.

This is what a competent engineer reaches for FIRST when asked to "flag integrity
problems in a decision packet": a single-pass keyword/regex scanner. It is NOT a
crippled strawman -- it makes a genuine, reasonable attempt at all the same finding
types the deterministic detectors target, using the surface heuristics a keyword
verifier actually has:

* contradictions  -- keyword-anchored cross-document number consistency: for a
                     lexicon of economic terms, pull the first number off any line
                     mentioning the term, and flag docs whose value differs from the
                     modal one. (A reasonable keyword-anchored cross-doc check.)
* unsupported     -- performance-claim flagging: any line naming a performance metric
                     (IRR / return / MOIC / TVPI / DPI) next to a number is flagged
                     for substantiation.

What it structurally CANNOT do -- and this is the measured wedge, not a rigged gap --
is re-derive the capital-account rollforward. A keyword scanner has no domain formula
model, so it never catches the arithmetic break. That is exactly the value the
deterministic, domain-modeled detector adds.

`naive_verify(docs)` returns findings in the same {type, doc, ...} shape as
`run_redteam`, so the two can be scored against the same labeled answer key.
"""
from __future__ import annotations

import re

# A reasonable keyword lexicon a first-cut engineer would use for a PE data room.
# Substring keywords (lowercased), NOT the tool's canonical anchored labels -- this
# is the naive approximation of the tool's schema-aware parsing.
_CONTRA_KEYWORDS = [
    "management fee",
    "carried interest",
    "preferred return",
    "hurdle",
    "lp commitment",
    "cumulative distributions",
    "ending capital account",
    "total commitments",
]
# performance-metric tokens a naive verifier flags for substantiation
_PERF_TOKENS = ["irr", "moic", "tvpi", "dpi", "rate of return", "annualized return"]
# a number that looks like a metric value: 45.0%, 1.16x, $431,000,000
_NUMBER = re.compile(r"(-?\$?\s*[\d,]+(?:\.\d+)?\s*[x%]?)", re.I)
_FIRST_NUM = re.compile(r"(-?[\d,]+(?:\.\d+)?)")


def _first_number(line: str):
    m = _FIRST_NUM.search(line)
    if not m:
        return None
    try:
        return float(m.group(1).replace(",", ""))
    except ValueError:
        return None


def naive_contradictions(docs: dict) -> list:
    """Keyword-anchored cross-document number consistency (the naive contradiction
    check): for each keyword, collect the first number on any line mentioning it,
    per document, and flag documents that differ from the modal value."""
    from collections import Counter

    findings = []
    for kw in _CONTRA_KEYWORDS:
        per_doc = {}
        for name, text in docs.items():
            for line in text.splitlines():
                if kw in line.lower():
                    v = _first_number(line)
                    if v is not None:
                        per_doc.setdefault(name, v)  # first hit per doc
                        break
        if len({round(v, 6) for v in per_doc.values()}) <= 1:
            continue
        counts = Counter(round(v, 6) for v in per_doc.values())
        modal = counts.most_common(1)[0][0]
        for name, v in per_doc.items():
            if round(v, 6) != modal:
                findings.append({
                    "type": "contradiction", "doc": name, "field": kw,
                    "detail": f"{kw!r} value {v:g} differs from modal {modal:g}",
                    "citation": f"{name}: {kw}",
                })
    return findings


def naive_unsupported(docs: dict) -> list:
    """Flag any line naming a performance metric next to a number as unsupported
    (the naive verifier cannot tell a math-derived MOIC from an unbacked IRR)."""
    findings = []
    for name, text in docs.items():
        for line in text.splitlines():
            low = line.lower()
            if any(tok in low for tok in _PERF_TOKENS) and _NUMBER.search(line):
                findings.append({
                    "type": "unsupported_claim", "doc": name, "field": "performance_claim",
                    "detail": f"line names a performance metric with a number: {line.strip()!r}",
                    "citation": f"{name}: {line.strip()}",
                })
    return findings


def naive_verify(docs) -> dict:
    """The naive baseline verifier. Same return shape as run_redteam."""
    docs = docs.docs if hasattr(docs, "docs") else docs
    findings = naive_contradictions(docs) + naive_unsupported(docs)
    hard = any(f["type"] == "contradiction" for f in findings)
    verdict = "high-risk" if hard else ("caution" if findings else "proceed")
    return {"verdict": verdict, "findings": findings}
