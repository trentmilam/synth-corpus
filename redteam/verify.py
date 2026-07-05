"""Deterministic red-team detectors + verdict.

Independent of the synth-corpus injector/checker (so scoring against its answer
key is honest): contradictions are found by comparing documents to EACH OTHER
(not to a hidden world truth); the arithmetic check is a fresh reconstruction;
the unsupported-claim check targets rate-of-return assertions that an
alternatives data room structurally cannot substantiate (no dated cash flows).
"""
from __future__ import annotations

import re
from collections import Counter

# canonical figure labels (the document schema)
LABELS = [
    "Management fee:",
    "Carried interest:",
    "Preferred return (hurdle):",
    "Total commitments (fund size):",
    "LP commitment:",
    "Cumulative distributions:",
    "Ending capital account (NAV):",
]
# negative currency is routine in PE data rooms (losses, capital returns): accept a
# minus sign either before the "$" (-$5,000,000) or after it ($-5,000,000).
_MONEY = re.compile(r"(-?)\$\s*(-?[\d,]+(?:\.\d+)?)")
_PCT = re.compile(r"([\d.]+)\s*%")
# "net IRR of 45.0%", "annualized return of 30%", "rate of return of 12%"
_RETURN = re.compile(r"(net\s+)?(irr|internal rate of return|annualized return|net return|rate of return)\s+of\s+([\d.]+)\s*%", re.I)


def _value_after(line: str, label: str):
    i = line.find(label)
    if i < 0:
        return None
    rest = line[i + len(label):]
    m = _MONEY.search(rest)
    if m:
        num = float(m.group(2).replace(",", ""))
        return -num if m.group(1) == "-" else num
    m = _PCT.search(rest)
    if m:
        return float(m.group(1))
    return None


def _figures(docs: dict) -> dict:
    """{label: {doc_name: value}} for every labeled figure found."""
    out = {lbl: {} for lbl in LABELS}
    for name, text in docs.items():
        for line in text.splitlines():
            s = line.strip()
            for lbl in LABELS:
                if s.startswith(lbl):
                    v = _value_after(s, lbl)
                    if v is not None:
                        out[lbl][name] = v
    return out


def detect_contradictions(docs: dict) -> list:
    """Same figure, different value across documents -> contradiction (the
    documents disagree with each other). The minority document(s) are flagged."""
    findings = []
    for lbl, per_doc in _figures(docs).items():
        if len({round(v, 6) for v in per_doc.values()}) <= 1:
            continue
        counts = Counter(round(v, 6) for v in per_doc.values())
        top_count = counts.most_common(1)[0][1]
        majority = [val for val, c in counts.items() if c == top_count]
        if len(majority) == 1:
            # a clear majority -> flag only the minority (disagreeing) documents
            modal = majority[0]
            for name, v in per_doc.items():
                if round(v, 6) != modal:
                    findings.append({
                        "type": "contradiction", "doc": name, "field": lbl.rstrip(":"),
                        "detail": f"{lbl} {v:g} disagrees with {modal:g} stated in other documents",
                        "citation": f"{name}: {lbl} {v:g}",
                    })
        else:
            # no majority (e.g. a 1-1 tie): we cannot tell which doc is correct, so
            # do NOT accuse either -- flag ALL conflicting docs as an unresolved conflict.
            others = sorted({round(v, 6) for v in per_doc.values()})
            for name, v in per_doc.items():
                disagree = [f"{o:g}" for o in others if o != round(v, 6)]
                findings.append({
                    "type": "contradiction", "doc": name, "field": lbl.rstrip(":"),
                    "detail": f"{lbl} {v:g} conflicts with {', '.join(disagree)} in other documents; "
                              f"no majority to resolve which is correct (unresolved conflict)",
                    "citation": f"{name}: {lbl} {v:g}",
                })
    return findings


def detect_unsupported_returns(docs: dict) -> list:
    """A rate-of-return (IRR / annualized return) assertion in the IC memo cannot
    be substantiated by an alternatives data room (which carries no dated cash
    flows) -> unverifiable."""
    findings = []
    for line in docs.get("ic_memo", "").splitlines():
        m = _RETURN.search(line)
        if m:
            findings.append({
                "type": "unsupported_claim", "doc": "ic_memo", "field": "return_claim",
                "detail": f"asserts a rate of return ({m.group(3)}%) with no dated cash flows in the data room to substantiate it",
                "citation": f"ic_memo: {line.strip()}",
            })
    return findings


def detect_arithmetic(docs: dict) -> list:
    """Reconstruct the capital-account rollforward and check it sums to the stated NAV."""
    ca = docs.get("capital_account", "")

    def g(lbl):
        for line in ca.splitlines():
            if line.strip().startswith(lbl):
                return _value_after(line.strip(), lbl)
        return None

    contrib = g("Contributions to date:")
    gain = g("Allocated net gain:")
    fees = g("Allocated management fees:")
    dist = g("Cumulative distributions:")
    nav = g("Ending capital account (NAV):")
    if None in (contrib, gain, fees, dist, nav):
        return []
    computed = contrib + gain - fees - dist
    if abs(computed - nav) > 1e-6:
        return [{
            "type": "arithmetic", "doc": "capital_account", "field": "rollforward",
            "detail": f"rollforward computes {computed:,.0f} but the statement reports {nav:,.0f}",
            "citation": "capital_account: capital account rollforward",
        }]
    return []


def run_redteam(corpus_or_docs) -> dict:
    docs = corpus_or_docs.docs if hasattr(corpus_or_docs, "docs") else corpus_or_docs
    findings = detect_contradictions(docs) + detect_unsupported_returns(docs) + detect_arithmetic(docs)
    hard = any(f["type"] in ("contradiction", "arithmetic") for f in findings)
    verdict = "high-risk" if hard else ("caution" if findings else "proceed")
    return {"verdict": verdict, "findings": findings}
