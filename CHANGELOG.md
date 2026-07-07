# Changelog

All notable changes to this project are documented in this file.

## [Unreleased]

### Fixed
- **Contradiction detection false negative**: `detect_contradictions`/`_figures` now match canonical
  figure labels case-insensitively and tolerant of whitespace/punctuation/word-order variance (e.g.
  "Fund Size / Total Commitments:" and "total commitments (fund size):" now resolve to the same
  label), instead of requiring byte-identical label text. A contradiction phrased differently in
  each document no longer silently evades detection.
- `unsupported_claim` finding text now states plainly that the detector flags every rate-of-return
  assertion for manual review and does not check whether it's substantiated elsewhere, instead of
  wording it as if a substantiation check had run.
- `coverage.labels_located` now always includes every canonical label (with an empty list for ones
  found in no document) and adds `coverage.labels_not_located`, so "never found" is an explicit,
  visible signal rather than an omitted dict key.
- README's head-to-head baseline table refreshed to match `eval/eval.py`'s actual current output;
  added `scripts/check_readme_numbers.py` (wired into CI) so the two can't silently drift apart again.
- Removed an uncited statistic and an unevidenced competitive claim from the README's rationale
  section.
- CI and the README's reproduction instructions now pin the companion synth-corpus checkout to a
  tagged release instead of a floating branch.

### Changed
- Deduplicated the sys.path/companion-repo bootstrap logic shared by `eval/eval.py` and
  `run_demo.py` into `synth_corpus_bootstrap.py`; both scripts' error message now points at the
  README's actual "Full reproduction" heading.

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
- **Fail-open verdict**: a broken or empty decision packet no longer returns the same
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
