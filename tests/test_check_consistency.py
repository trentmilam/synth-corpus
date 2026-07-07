"""Direct pytest coverage of the `check_consistency()` seed-pairing safety:
the one-arg Corpus form is mismatch-proof; a provable seed mismatch raises; and
the unverifiable bare-dict `(docs, world)` form warns loudly instead of silently
returning a fabricated finding set.
"""
import json
import warnings

import pytest

from synthfin.check import check_consistency
from synthfin.generate import generate
from synthfin.world import build_world

SEED = 20260704
WRONG_SEED = 999


def _mismatched_corpus():
    return generate(SEED, injects=[{"type": "contradiction", "doc": "ddq", "field": "management_fee"}])


def _is_the_one_contradiction(findings):
    return (len(findings) == 1 and findings[0]["type"] == "contradiction"
            and findings[0]["doc"] == "ddq" and findings[0]["field"] == "management_fee")


def test_bare_dict_wrong_world_warns():
    """A bare docs dict (no seed) scored against a World built from the wrong
    seed must warn, not silently return findings."""
    c = _mismatched_corpus()
    with pytest.warns(UserWarning):
        check_consistency(c.docs, build_world(WRONG_SEED))


def test_corpus_plus_wrong_world_raises():
    """A provable seed mismatch (Corpus carries a seed, World carries a
    different one) must raise -- never silently fabricate findings."""
    c = _mismatched_corpus()
    with pytest.raises(ValueError):
        check_consistency(c, build_world(WRONG_SEED))


def test_onearg_corpus_is_safe_and_silent():
    """The mismatch-proof form: one-arg Corpus derives the world from its own
    seed, finds exactly the one real contradiction, and emits no warning."""
    c = _mismatched_corpus()
    with warnings.catch_warnings():
        warnings.simplefilter("error")  # any warning becomes a test failure
        findings = check_consistency(c)
    assert _is_the_one_contradiction(findings)


def test_omitted_world_on_bare_dict_raises():
    """Omitting `world` is only valid for a Corpus; a bare dict has no seed to
    derive a world from, so it must raise rather than guess."""
    c = _mismatched_corpus()
    with pytest.raises(ValueError):
        check_consistency(c.docs)


def test_manifest_reload_roundtrip_is_safe():
    """Persist-manifest-then-reload-and-score stays safe: passing the reloaded
    manifest dict as `world` alongside the Corpus cross-checks both seeds (no
    warn, no raise) and reaches the same correct finding set as the one-arg form."""
    c = _mismatched_corpus()
    reloaded_manifest = json.loads(json.dumps(c.manifest))  # simulate manifest.json round trip
    with warnings.catch_warnings():
        warnings.simplefilter("error")
        findings = check_consistency(c, reloaded_manifest)
    assert findings == check_consistency(c)
    assert _is_the_one_contradiction(findings)


def test_matching_world_scores_clean_corpus():
    clean = generate(SEED)
    assert check_consistency(clean) == []
