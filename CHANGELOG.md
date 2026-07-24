# Changelog

All notable changes to this project are documented in this file.

## [Unreleased]

### Fixed
- `detect_contradictions`/`_figures` now match canonical figure labels case/whitespace/
  punctuation/word-order-tolerant (e.g. "Fund Size / Total Commitments:" and "total commitments
  (fund size):" resolve to the same label) instead of requiring byte-identical text.
- `unsupported_claim` finding text now states plainly it flags every rate-of-return assertion for
  manual review, not that a substantiation check ran.
- `coverage.labels_located` now always includes every canonical label; added
  `coverage.labels_not_located` as an explicit signal.
- README's head-to-head baseline table refreshed to match `eval/eval.py`'s live output; added
  `scripts/check_readme_numbers.py` (CI-wired) so they can't drift apart again.
- Removed an uncited statistic and an unevidenced competitive claim from the README.
- CI and README reproduction instructions now pin the companion synth-corpus checkout to a tagged
  release instead of a floating branch.

### Changed
- Deduplicated the sys.path/companion-repo bootstrap logic shared by `eval/eval.py` and
  `run_demo.py` into `synth_corpus_bootstrap.py`.

## [0.1.0] - 2026-07-07

### Added
- `pyproject.toml` packaging (the `redteam` package is pure stdlib, zero required dependencies).
- `tests/test_verify.py` pytest suite (zero-dependency detector tests, including fail-open and
  money-formatting regressions).
- `.github/workflows/eval.yml` CI: runs the pytest suite and the full synth-corpus-backed eval on
  every push/PR.
- `coverage` field on `run_redteam`'s return value, and a distinct `insufficient-data` verdict for
  when the capital-account rollforward cannot be verified (missing or unmatched labels).
- Input validation (`validate_docs`) at the `run_redteam`/`naive_verify` entrypoints.

### Fixed
- Fail-open verdict (silently treating a broken input as if it had passed, instead of flagging the
  failure): a broken or empty decision packet no longer returns the same
  `{'verdict': 'proceed', 'findings': []}` as a genuinely clean one.
- Money-valued contradiction citations (fund size, LP commitment, distributions, NAV) now render
  with thousands separators (`500,000,000`) instead of scientific notation (`5e+08`).
- A duplicate canonical label within one document with conflicting values now raises instead of
  silently keeping only the last-seen value.

## [0.0.1] - 2026-07-05

### Added
- Initial deterministic red-team detectors: cross-document contradictions, unsupported
  performance claims, arithmetic (capital-account rollforward) errors.
- Naive keyword/regex baseline (`redteam/baseline.py`) for head-to-head comparison.
