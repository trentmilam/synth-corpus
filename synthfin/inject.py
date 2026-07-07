"""Labeled flaw injection: plant controlled defects and record the answer key.

Each injection returns a label ``{type, doc, field, truth, injected}`` so a
downstream tool can be scored against ground truth. Supported:

* ``contradiction``   -- change a canonical figure in one doc to disagree with the world.
* ``arithmetic_error``-- break the capital-account rollforward (change one input line,
                         leave the stated NAV) so it no longer sums.
* ``ungrounded_claim``-- append a claim to the IC memo asserting a metric absent from
                         the data room (nothing in the corpus supports it).

Vocabulary note: this module's answer key records a broken rollforward as flaw type
``"arithmetic_error"``, while `check.py`'s detectors report the same defect class as
finding type ``"arithmetic"``. This split is intentional and NOT unified -- see
`check.py`'s module docstring and the README for the mapping a downstream caller needs.
"""
from __future__ import annotations

import re

from .render import fmt_money, fmt_pct, LBL_ALLOC_GAIN
from .check import FIELDS, _PCT, _MONEY


def _has_label(text: str, label: str) -> bool:
    return any(line.strip().startswith(label) for line in text.splitlines())


def _set_label_line(text: str, label: str, new_value_str: str) -> str:
    out = []
    for line in text.splitlines():
        if line.strip().startswith(label):
            indent = line[: len(line) - len(line.lstrip())]
            out.append(f"{indent}{label} {new_value_str}")
        else:
            out.append(line)
    return "\n".join(out)


def _wrong(truth: float, kind: str):
    return round(truth + 1.0, 1) if kind == _PCT else float(truth) * 2.0


def apply_injects(docs: dict, world, injects: list):
    docs = dict(docs)
    flaws = []
    for inj in injects:
        typ = inj["type"]

        if typ == "contradiction":
            if "doc" not in inj:
                raise ValueError(f"contradiction inject missing required key 'doc': {inj!r}")
            if "field" not in inj:
                raise ValueError(f"contradiction inject missing required key 'field': {inj!r}")
            doc = inj["doc"]
            field = inj["field"]
            if field not in FIELDS:
                raise ValueError(f"unknown field {field!r}; must be one of {sorted(FIELDS)}")
            if doc not in docs:
                raise ValueError(f"unknown doc {doc!r}; must be one of {sorted(docs)}")
            label, _docs, truth_fn, kind = FIELDS[field]
            truth = float(truth_fn(world))
            injected = float(inj.get("value", _wrong(truth, kind)))
            # A recorded flaw must be a REAL, present defect. Reject no-op injects:
            #   (a) the target doc does not carry this field's label (nothing to change),
            #   (b) the injected value equals the world truth (contradicts nothing).
            if not _has_label(docs[doc], label):
                raise ValueError(
                    f"no-op contradiction: doc {doc!r} carries no {label!r} line for field {field!r}")
            if abs(injected - truth) <= 1e-6:
                raise ValueError(
                    f"no-op contradiction: injected value {injected} equals world truth for {field!r}")
            val_str = fmt_pct(injected) if kind == _PCT else fmt_money(injected)
            truth_str = fmt_pct(truth) if kind == _PCT else fmt_money(truth)
            # Final guard: the RENDERED figure must actually differ (e.g. sub-rounding money).
            if val_str == truth_str:
                raise ValueError(
                    f"no-op contradiction: rendered {label!r} unchanged in doc {doc!r} for field {field!r}")
            docs[doc] = _set_label_line(docs[doc], label, val_str)
            flaws.append({"type": typ, "doc": doc, "field": field, "truth": truth, "injected": injected})

        elif typ == "arithmetic_error":
            # inflate the allocated-net-gain input; leave the stated NAV -> rollforward breaks
            delta = float(inj.get("delta", 7_000_000))
            truth_gain = float(world.lp_allocated_gain)
            bad = truth_gain + delta
            # A recorded flaw must be a REAL break: a zero (or sub-rounding) delta leaves the
            # RENDERED gain equal to truth, so the rollforward still sums to NAV -- no error.
            if fmt_money(bad) == fmt_money(truth_gain):
                raise ValueError(
                    f"no-op arithmetic_error: delta {delta} leaves the rollforward summing to NAV")
            docs["capital_account"] = _set_label_line(docs["capital_account"], LBL_ALLOC_GAIN, fmt_money(bad))
            flaws.append({"type": typ, "doc": "capital_account", "field": "allocated_net_gain",
                          "truth": float(world.lp_allocated_gain), "injected": bad})

        elif typ == "ungrounded_claim":
            claim = inj.get("text", "The Fund has achieved a net IRR of 45.0% since inception.")
            # A recorded flaw must plant real text; an empty claim adds nothing to ground.
            if not claim.strip():
                raise ValueError("no-op ungrounded_claim: empty claim text plants nothing")
            docs["ic_memo"] = docs["ic_memo"].rstrip() + "\n\n" + claim + "\n"
            flaws.append({"type": typ, "doc": "ic_memo", "field": inj.get("field", "net_irr_claim"),
                          "truth": None, "injected": claim})

        else:
            raise ValueError(f"unknown inject type: {typ!r}")

    return docs, flaws
