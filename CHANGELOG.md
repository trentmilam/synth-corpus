# Changelog

All notable changes to this project are documented in this file.

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
