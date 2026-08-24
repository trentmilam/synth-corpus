"""pytest suite for redteam/verify.py + redteam/baseline.py.

Zero dependencies beyond the stdlib and pytest -- no synth-corpus, no numpy.
Run from the repo root:

    python -m pytest tests/ -v
"""
import pytest

from redteam.verify import (
    capital_account_coverage,
    detect_arithmetic,
    detect_contradictions,
    run_redteam,
    validate_docs,
    _figures,
)
from redteam.baseline import naive_verify


# --- fail-open regression -- "could not check" must never look like -------
# --- "checked, and it's clean" ------------------------------------------------

def test_empty_docs_is_insufficient_data_not_proceed():
    report = run_redteam({})
    assert report["verdict"] != "proceed"
    assert report["verdict"] == "insufficient-data"
    assert report["findings"] == []


def test_garbage_unmatched_doc_is_insufficient_data_not_proceed():
    report = run_redteam({"ic_memo": "garbage text with no recognizable labels"})
    assert report["verdict"] != "proceed"
    assert report["verdict"] == "insufficient-data"


def test_reworded_label_hides_broken_nav_but_verdict_is_not_proceed():
    """The NAV is overstated by ~$1.8-2.0M, but only because one label was reworded
    ("Mgmt fees allocated:" instead of the canonical "Allocated management
    fees:"). The rollforward literally cannot be checked -- the verdict must
    say so, not silently report proceed."""
    broken = {"capital_account": (
        "Contributions to date: $10,000,000\n"
        "Allocated net gain: $2,000,000\n"
        "Mgmt fees allocated: $200,000\n"              # reworded -- unrecognized
        "Cumulative distributions: $1,000,000\n"
        "Ending capital account (NAV): $12,800,000\n"  # unverified overstatement
    )}
    report = run_redteam(broken)
    assert report["verdict"] != "proceed"
    assert report["verdict"] == "insufficient-data"
    assert "Allocated management fees:" in report["coverage"]["capital_account_fields_missing"]


def test_fully_labeled_clean_packet_is_proceed():
    clean = {"capital_account": (
        "Contributions to date: $10,000,000\n"
        "Allocated net gain: $2,000,000\n"
        "Allocated management fees: $200,000\n"
        "Cumulative distributions: $1,000,000\n"
        "Ending capital account (NAV): $10,800,000\n"
    )}
    report = run_redteam(clean)
    assert report["verdict"] == "proceed"
    assert report["findings"] == []
    assert report["coverage"]["capital_account_fields_missing"] == []


def test_correctly_labeled_broken_rollforward_is_high_risk():
    """Contrast case for the reworded-label test above: when every label IS
    canonical, a genuine break is still caught as high-risk (proves the fix
    didn't just downgrade every failure to insufficient-data)."""
    broken = {"capital_account": (
        "Contributions to date: $10,000,000\n"
        "Allocated net gain: $2,000,000\n"
        "Allocated management fees: $200,000\n"
        "Cumulative distributions: $1,000,000\n"
        "Ending capital account (NAV): $12,800,000\n"  # should be $10,800,000
    )}
    report = run_redteam(broken)
    assert report["verdict"] == "high-risk"
    assert any(f["type"] == "arithmetic" for f in report["findings"])


def test_capital_account_coverage_reports_found_and_missing():
    coverage = capital_account_coverage({"capital_account": "Contributions to date: $1,000,000\n"})
    assert coverage["found"] == ["Contributions to date:"]
    assert "Ending capital account (NAV):" in coverage["missing"]


# --- money-valued contradiction citations must not be scientific notation ---

def test_money_magnitude_contradiction_with_majority_is_not_scientific_notation():
    docs = {
        "ppm": "Total commitments (fund size): $500,000,000\n",
        "lpa": "Total commitments (fund size): $500,000,000\n",
        "ddq": "Total commitments (fund size): $450,000,000\n",
    }
    findings = detect_contradictions(docs)
    assert len(findings) == 1
    detail, citation = findings[0]["detail"], findings[0]["citation"]
    assert findings[0]["doc"] == "ddq"
    assert "500,000,000" in detail
    assert "450,000,000" in detail
    assert "e+" not in detail.lower()
    assert "e+" not in citation.lower()


def test_money_magnitude_contradiction_tie_is_not_scientific_notation():
    """A two-doc $500M/$450M disagreement (no majority) must still render
    plainly, in both docs' citations."""
    docs = {
        "ppm": "Total commitments (fund size): $500,000,000\n",
        "ddq": "Total commitments (fund size): $450,000,000\n",
    }
    findings = detect_contradictions(docs)
    assert len(findings) == 2
    for f in findings:
        assert "e+" not in f["detail"].lower()
        assert "e+" not in f["citation"].lower()
    assert any("500,000,000" in f["detail"] for f in findings)
    assert any("450,000,000" in f["detail"] for f in findings)


def test_percentage_contradiction_still_compact():
    docs = {
        "ppm": "Preferred return (hurdle): 9.0%\n",
        "lpa": "Preferred return (hurdle): 8.0%\n",
        "ddq": "Preferred return (hurdle): 8.0%\n",
    }
    findings = detect_contradictions(docs)
    assert len(findings) == 1
    assert findings[0]["doc"] == "ppm"


# --- existing redcases (ported from eval.py) ---------------------------------

def test_negative_rollforward_break_is_caught_not_fail_open():
    neg_broken = {"capital_account": (
        "Contributions to date: $10,000,000\n"
        "Allocated net gain: $-5,000,000\n"
        "Allocated management fees: $200,000\n"
        "Cumulative distributions: $1,000,000\n"
        "Ending capital account (NAV): $9,000,000\n"  # 3,800,000 != 9,000,000
    )}
    assert len(detect_arithmetic(neg_broken)) == 1


def test_negative_rollforward_correct_is_clean():
    neg_clean = {"capital_account": (
        "Contributions to date: $10,000,000\n"
        "Allocated net gain: $-5,000,000\n"
        "Allocated management fees: $200,000\n"
        "Cumulative distributions: $1,000,000\n"
        "Ending capital account (NAV): $3,800,000\n"
    )}
    assert detect_arithmetic(neg_clean) == []


def test_two_doc_tie_flags_both_not_just_one():
    two_doc = {
        "ppm": "Preferred return (hurdle): 9.0%\n",
        "lpa": "Preferred return (hurdle): 8.0%\n",
    }
    tie = detect_contradictions(two_doc)
    assert {f["doc"] for f in tie} == {"ppm", "lpa"}
    assert all("unresolved conflict" in f["detail"] for f in tie)


# --- duplicate label within one document must not silently overwrite -------

def test_duplicate_label_same_value_is_harmless():
    docs = {"ppm": "Management fee: 2.0%\nManagement fee: 2.0%\n"}
    figures = _figures(docs)
    assert figures["Management fee:"]["ppm"] == 2.0


def test_duplicate_label_conflicting_value_fails_loud():
    docs = {"ppm": "Management fee: 2.0%\nManagement fee: 3.0%\n"}
    with pytest.raises(ValueError):
        _figures(docs)


# --- input validation --------------------------------------------------------

def test_validate_docs_rejects_non_dict():
    with pytest.raises(TypeError):
        validate_docs(["not", "a", "dict"])


def test_validate_docs_rejects_non_string_values():
    with pytest.raises(TypeError):
        validate_docs({"ppm": 12345})


def test_validate_docs_rejects_oversized_document():
    with pytest.raises(ValueError):
        validate_docs({"ppm": "x" * 3_000_000})


def test_run_redteam_rejects_bad_input():
    with pytest.raises(TypeError):
        run_redteam("not a docs dict")


def test_naive_verify_rejects_bad_input():
    with pytest.raises(TypeError):
        naive_verify(12345)


def test_naive_verify_accepts_valid_docs():
    report = naive_verify({"ic_memo": "net IRR of 45.0%\n"})
    assert report["verdict"] in ("proceed", "caution", "high-risk")


# --- label matching must tolerate case/whitespace/word-order variance ------
# --- (a real contradiction must not go unnoticed just because the two ------
# --- documents phrase the same figure's label differently) -----------------

def test_case_and_wording_variant_labels_still_catch_a_real_contradiction():
    """A material contradiction must be caught even when neither document
    uses the byte-identical canonical label text -- only case, punctuation,
    and word order differ, not the meaning."""
    docs = {
        "ppm": "Fund Size / Total Commitments: $500,000,000\n",
        "ddq": "total commitments (fund size): $450,000,000\n",
    }
    report = run_redteam(docs)
    assert report["verdict"] == "high-risk"
    assert any(f["type"] == "contradiction" for f in report["findings"])


def test_case_variant_label_alone_is_recognized_by_figures():
    docs = {"ppm": "MANAGEMENT FEE: 2.0%\n"}
    figures = _figures(docs)
    assert figures["Management fee:"]["ppm"] == 2.0


def test_genuinely_different_wording_is_not_matched():
    """Matching tolerates case/whitespace/word-order noise on the SAME
    label, but must not match a different label or free-text prose as if it
    were a canonical figure."""
    docs = {"ppm": "Some unrelated note about the fund's fee structure: 2.0%\n"}
    figures = _figures(docs)
    assert figures["Management fee:"] == {}


# --- coverage must make "never located" a visible, explicit signal ---------

def test_labels_not_located_lists_labels_missing_from_every_document():
    report = run_redteam({"ppm": "Management fee: 2.0%\n"})
    assert report["coverage"]["labels_located"]["Management fee:"] == ["ppm"]
    assert "Carried interest:" in report["coverage"]["labels_not_located"]
    assert "Management fee:" not in report["coverage"]["labels_not_located"]


# --- the unsupported_claim finding must describe what it actually does -----

def test_unsupported_claim_detail_does_not_imply_a_substantiation_check():
    report = run_redteam({"ic_memo": "The Fund has achieved a net IRR of 22.4%.\n"})
    finding = next(f for f in report["findings"] if f["type"] == "unsupported_claim")
    detail = finding["detail"].lower()
    assert "does not check" in detail or "not check" in detail
    assert "no dated cash flows in the data room to substantiate it" not in detail
