"""Deterministic red-team detectors + verdict.

Independent of the synth-corpus injector/checker (so scoring against its answer
key is honest): contradictions are found by comparing documents to EACH OTHER
(not to a hidden world truth); the arithmetic check is a fresh reconstruction;
the unsupported-claim check targets rate-of-return assertions that an
alternatives data room structurally cannot substantiate (no dated cash flows).

Expected `docs` schema
-----------------------
`docs` is a `dict[str, str]` mapping a document name to its raw text. Canonical
document names (not all are required -- see per-check notes below): `ppm`,
`lpa`, `ddq`, `adv`, `k1`, `capital_account`, `ic_memo`.

- `detect_contradictions` scans EVERY document for any line that starts with
  one of the canonical figure labels in `LABELS` below (exact strings,
  including the trailing colon); a contradiction only fires once the SAME
  label is found with DIFFERENT values in >=2 documents.
- `detect_unsupported_returns` only reads `docs["ic_memo"]`.
- `detect_arithmetic` requires `docs["capital_account"]` to contain all five
  canonical rollforward labels in `CAPITAL_ACCOUNT_LABELS` below, each
  starting its own line, verbatim (a reworded label, e.g. "Mgmt fees
  allocated:" instead of the canonical "Allocated management fees:", will NOT
  be recognized). If any is missing or unmatched the rollforward cannot be
  verified -- see `capital_account_coverage` and the `insufficient-data`
  verdict below.

Verdict semantics (`run_redteam`)
----------------------------------
- `high-risk`         -- a contradiction or arithmetic-break finding fired.
- `caution`           -- only an unsupported-claim finding fired.
- `insufficient-data` -- no findings fired AND the capital_account rollforward
  could not be verified (a required label was missing/unmatched). This is
  DISTINCT from `proceed` on purpose: "nothing was checked" must never look
  identical to "checked, and it's clean."
- `proceed`           -- no findings fired AND the capital_account rollforward
  was fully verified.

The returned dict also carries a `coverage` field recording which canonical
labels were actually located (and in which documents), so a caller can tell
"checked, clean" apart from "couldn't check" at a glance.
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
# money-valued labels: rendered with thousands separators (matching
# detect_arithmetic's convention), never Python's {:g} -- which flips to
# unreadable scientific notation ("5e+08") for any value >= 1e6, i.e. most
# dollar figures this tool exists to check. The rest of LABELS are percentages.
_MONEY_LABELS = {
    "Total commitments (fund size):",
    "LP commitment:",
    "Cumulative distributions:",
    "Ending capital account (NAV):",
}
# the canonical capital-account rollforward labels detect_arithmetic requires,
# each starting its own line in docs["capital_account"], verbatim.
CAPITAL_ACCOUNT_LABELS = [
    "Contributions to date:",
    "Allocated net gain:",
    "Allocated management fees:",
    "Cumulative distributions:",
    "Ending capital account (NAV):",
]
# negative currency is routine in PE data rooms (losses, capital returns): accept a
# minus sign either before the "$" (-$5,000,000) or after it ($-5,000,000).
_MONEY = re.compile(r"(-?)\$\s*(-?[\d,]+(?:\.\d+)?)")
_PCT = re.compile(r"([\d.]+)\s*%")
# "net IRR of 45.0%", "annualized return of 30%", "rate of return of 12%"
_RETURN = re.compile(r"(net\s+)?(irr|internal rate of return|annualized return|net return|rate of return)\s+of\s+([\d.]+)\s*%", re.I)

# input-validation limits for run_redteam/naive_verify (both process untrusted
# third-party documents, so the public entrypoints assert shape rather than
# duck-type it).
MAX_DOCS = 64
MAX_DOC_CHARS = 2_000_000


def validate_docs(docs) -> None:
    """Assert `docs` is a `dict[str, str]` within sane size bounds.

    Raises TypeError/ValueError with a clear message instead of letting a
    malformed input surface as an unhandled AttributeError/TypeError deeper
    inside the detectors.
    """
    if not isinstance(docs, dict):
        raise TypeError(f"docs must be a dict[str, str]; got {type(docs).__name__}")
    if len(docs) > MAX_DOCS:
        raise ValueError(f"too many documents ({len(docs)} > {MAX_DOCS} cap)")
    for name, text in docs.items():
        if not isinstance(name, str) or not isinstance(text, str):
            raise TypeError(
                f"docs must be dict[str, str]; got key {name!r} "
                f"({type(name).__name__}) -> value type {type(text).__name__}"
            )
        if len(text) > MAX_DOC_CHARS:
            raise ValueError(f"document {name!r} exceeds size cap ({len(text)} > {MAX_DOC_CHARS} chars)")


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


def _labeled_value(text: str, label: str):
    """First value found on a line of `text` that starts with `label`."""
    for line in text.splitlines():
        if line.strip().startswith(label):
            return _value_after(line.strip(), label)
    return None


def _fmt(v: float, lbl: str) -> str:
    """Render a labeled figure for a finding's detail/citation text. Money
    labels use thousands separators (never scientific notation); the rest
    (percentages) keep the compact {:g} form."""
    return f"{v:,.0f}" if lbl in _MONEY_LABELS else f"{v:g}"


def _figures(docs: dict) -> dict:
    """{label: {doc_name: value}} for every labeled figure found.

    Raises ValueError if the same canonical label appears more than once
    within a single document with a DIFFERING value -- silently keeping only
    the last occurrence would hide an intra-document contradiction (the label
    disagreeing with itself), so this is a fail-loud invariant rather than a
    silent overwrite. A label repeating the same value twice is harmless and
    does not raise.
    """
    out = {lbl: {} for lbl in LABELS}
    for name, text in docs.items():
        for line in text.splitlines():
            s = line.strip()
            for lbl in LABELS:
                if s.startswith(lbl):
                    v = _value_after(s, lbl)
                    if v is not None:
                        if name in out[lbl] and out[lbl][name] != v:
                            raise ValueError(
                                f"document {name!r} states {lbl!r} more than once with "
                                f"different values ({out[lbl][name]!r} and {v!r}); each "
                                "canonical label must appear at most once per document"
                            )
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
                        "detail": f"{lbl} {_fmt(v, lbl)} disagrees with {_fmt(modal, lbl)} stated in other documents",
                        "citation": f"{name}: {lbl} {_fmt(v, lbl)}",
                    })
        else:
            # no majority (e.g. a 1-1 tie): we cannot tell which doc is correct, so
            # do NOT accuse either -- flag ALL conflicting docs as an unresolved conflict.
            others = sorted({round(v, 6) for v in per_doc.values()})
            for name, v in per_doc.items():
                disagree = [_fmt(o, lbl) for o in others if o != round(v, 6)]
                findings.append({
                    "type": "contradiction", "doc": name, "field": lbl.rstrip(":"),
                    "detail": f"{lbl} {_fmt(v, lbl)} conflicts with {', '.join(disagree)} in other documents; "
                              f"no majority to resolve which is correct (unresolved conflict)",
                    "citation": f"{name}: {lbl} {_fmt(v, lbl)}",
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
    contrib = _labeled_value(ca, "Contributions to date:")
    gain = _labeled_value(ca, "Allocated net gain:")
    fees = _labeled_value(ca, "Allocated management fees:")
    dist = _labeled_value(ca, "Cumulative distributions:")
    nav = _labeled_value(ca, "Ending capital account (NAV):")
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


def capital_account_coverage(docs: dict) -> dict:
    """Which of the canonical `CAPITAL_ACCOUNT_LABELS` were actually located
    (and parsed to a numeric value) in `docs["capital_account"]`.

    This is the coverage/unverifiable signal `run_redteam` uses to distinguish
    "the rollforward was checked and it's clean" from "the rollforward could
    not be checked" (e.g. a required label is missing or reworded) -- the two
    must never collapse into the same verdict.
    """
    ca = docs.get("capital_account", "")
    found = [lbl for lbl in CAPITAL_ACCOUNT_LABELS if _labeled_value(ca, lbl) is not None]
    missing = [lbl for lbl in CAPITAL_ACCOUNT_LABELS if lbl not in found]
    return {"found": found, "missing": missing}


def run_redteam(corpus_or_docs) -> dict:
    docs = corpus_or_docs.docs if hasattr(corpus_or_docs, "docs") else corpus_or_docs
    validate_docs(docs)
    findings = detect_contradictions(docs) + detect_unsupported_returns(docs) + detect_arithmetic(docs)
    ca_coverage = capital_account_coverage(docs)

    hard = any(f["type"] in ("contradiction", "arithmetic") for f in findings)
    if hard:
        verdict = "high-risk"
    elif findings:
        verdict = "caution"
    elif ca_coverage["missing"]:
        # nothing was found wrong, but the rollforward -- the tool's own core
        # check -- could not be verified at all; never render this as "proceed".
        verdict = "insufficient-data"
    else:
        verdict = "proceed"

    coverage = {
        "capital_account_fields_found": ca_coverage["found"],
        "capital_account_fields_missing": ca_coverage["missing"],
        "labels_located": {lbl: sorted(per_doc) for lbl, per_doc in _figures(docs).items() if per_doc},
    }
    return {"verdict": verdict, "findings": findings, "coverage": coverage}
