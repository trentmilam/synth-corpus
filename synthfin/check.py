"""Consistency checker: does the corpus tie out to the world state?

For each canonical labeled figure, extract its value from every document that
carries it and compare to the world truth -> a mismatch is a `contradiction`
finding. Separately, re-derive the capital-account rollforward from its own lines
and verify the equation -> a mismatch is an `arithmetic` finding.

This is what a clean corpus must pass (0 findings) and what makes injected flaws
detectable at exactly their labeled locations.

`check_consistency()` is a reference oracle: its whole job is being a trustworthy
answer key, so scoring `docs` against the wrong `world` must never pass silently.
The mismatch-proof way to call it is the one-argument Corpus form --
``check_consistency(corpus)`` -- which derives the world from the corpus's own
recorded seed (structurally impossible to mismatch). See the docstring on
`check_consistency` for every accepted input form, the raise-on-mismatch guard,
and the unverifiable-pairing warning on the bare ``(docs, world)`` form.

Vocabulary note: findings emitted here (and by `detect_worldfree`/`detect_naive`)
use the type name ``"arithmetic"`` for a broken capital-account rollforward, while
`inject.py`'s answer key records the same defect class as ``"arithmetic_error"``.
The two vocabularies are intentionally NOT unified (renaming either is a breaking
change for downstream integrators keyed on one or the other) -- a caller comparing
findings against `manifest["flaws"]` must map between them itself; see
`eval/eval.py`'s `_key()` for the reference mapping.
"""
from __future__ import annotations

import re
import warnings
from collections import Counter

from .render import (
    LBL_MGMT_FEE, LBL_CARRY, LBL_HURDLE, LBL_FUND_SIZE, LBL_LP_COMMIT,
    LBL_DISTRIB, LBL_ENDING_NAV, LBL_CONTRIB, LBL_ALLOC_GAIN, LBL_ALLOC_FEES,
)
from .world import build_world

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


# Public aliases -- prefer these over the underscore-prefixed names above when
# importing from outside this module (e.g. from a test harness or example).
value_after_label = _value_after_label
MONEY = _MONEY
PCT = _PCT


def _corpus_seed(obj):
    """If `obj` carries a `.manifest` dict (i.e. it is a `Corpus`), return its
    recorded seed; otherwise None. Duck-typed to avoid importing `Corpus` from
    `.generate`, which would create a circular import (generate -> inject -> check)."""
    manifest = getattr(obj, "manifest", None)
    if isinstance(manifest, dict):
        return manifest.get("seed")
    return None


def _resolve_world(world):
    """Normalize the `world` argument of `check_consistency` to an actual
    `World` instance, plus the seed it corresponds to (or None if unknown).

    Accepts:
      - a `World` instance (from `build_world()`) -- used as-is.
      - a `Corpus` instance -- its `manifest['seed']` rebuilds the matching
        `World` internally, so the corpus can be re-scored without the caller
        having to separately remember the seed.
      - a manifest dict, e.g. `corpus.manifest` OR `corpus.manifest['world']`
        (a `World.summary()` dict -- both carry a `'seed'` key) -- likewise
        rebuilds the `World` from that seed. This is the safe way to re-score
        a corpus after persisting `manifest.json` and reloading it: pass the
        reloaded manifest dict here directly instead of trying to hand a
        plain dict to code that expects `World` attributes.
    """
    corpus_seed = _corpus_seed(world)
    if corpus_seed is not None:
        return build_world(corpus_seed), corpus_seed
    if isinstance(world, dict):
        if "seed" not in world:
            raise ValueError(
                "check_consistency: `world` dict has no 'seed' key -- pass a "
                "Corpus, a Corpus.manifest, a World.summary() dict "
                "(manifest['world']), or a World instance (build_world(seed))"
            )
        return build_world(world["seed"]), world["seed"]
    return world, getattr(world, "seed", None)


_UNVERIFIABLE_PAIRING_WARNING = (
    "check_consistency: `docs` is a plain dict that carries no seed, so its "
    "pairing with the supplied `world` cannot be verified -- it is trusted "
    "exactly as passed. Grading docs against a World built from a DIFFERENT "
    "seed silently produces fabricated findings. For a mismatch-proof call, "
    "pass the Corpus itself -- check_consistency(corpus) -- which derives the "
    "world from the corpus's own recorded seed."
)


def check_consistency(docs, world=None) -> list:
    """Score `docs` against a world and return the list of findings.

    Preferred, mismatch-proof form -- pass the `Corpus`::

        check_consistency(corpus)

    The world is rebuilt internally from `corpus.manifest['seed']`, so it is
    structurally impossible to grade a corpus against a world that did not
    produce it.

    `docs` may be a `Corpus` or a plain `dict[str, str]` (as in `Corpus.docs`).
    `world` may be omitted (only valid when `docs` is a `Corpus`), or given as a
    `World`, a `Corpus`, or a manifest-shaped dict (`corpus.manifest` or
    `corpus.manifest['world']` -- both carry a `'seed'`, resolved via
    `_resolve_world`).

    Safety semantics:

    * `world` omitted and `docs` is a plain dict -> `ValueError` (no seed to
      derive a world from).
    * a seed is recoverable from BOTH sides and they differ -> `ValueError`
      (raise-on-mismatch; never silently grade against the wrong world).
    * `docs` is a plain dict (no recoverable seed) and a `world` is supplied ->
      a `UserWarning` is emitted EVERY time (matched or not): the pairing is
      caller-asserted and cannot be verified, so the classic silent-wrong
      hazard -- `check_consistency(corpus.docs, build_world(WRONG_SEED))` --
      now warns loudly instead of returning a fabricated finding set.
    """
    docs_seed = _corpus_seed(docs)
    docs_map = docs.docs if docs_seed is not None else docs

    if world is None:
        if docs_seed is None:
            raise ValueError(
                "check_consistency: `world` omitted but `docs` is a plain dict "
                "with no recoverable seed -- pass a Corpus "
                "(check_consistency(corpus)) so the world can be derived "
                "internally, or supply the matching World "
                "(check_consistency(docs, build_world(seed)))."
            )
        world, world_seed = build_world(docs_seed), docs_seed
    else:
        world, world_seed = _resolve_world(world)
        if docs_seed is not None and world_seed is not None and docs_seed != world_seed:
            raise ValueError(
                f"check_consistency: seed mismatch -- docs were generated from seed "
                f"{docs_seed!r}, but `world` corresponds to seed {world_seed!r}. "
                "Scoring docs against a World that did not produce them would "
                "silently fabricate findings; pass the matching Corpus/manifest, "
                "or a World built from the same seed as docs."
            )
        if docs_seed is None:
            warnings.warn(_UNVERIFIABLE_PAIRING_WARNING, UserWarning, stacklevel=2)

    docs = docs_map

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
