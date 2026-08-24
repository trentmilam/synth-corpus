"""Guard against README.md's head-to-head baseline table drifting away from
`eval/eval_redteam.py`'s actual output.

Runs `eval/eval_redteam.py` fresh, parses its printed HEAD-TO-HEAD numbers, parses
the README's checked-in table, and fails (non-zero exit) if they don't match
exactly. Run locally after any change that could move the numbers, or in CI
on every push/PR -- this is what should have caught the numbers going stale
before they were ever published.

    python scripts/check_readme_numbers.py
"""
from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
README = ROOT / "README.md"
EVAL_SCRIPT = ROOT / "eval" / "eval_redteam.py"

_README_ROW_RE = re.compile(
    r"\|\s*(deterministic \(this tool\)|naive keyword baseline)\s*\|\s*"
    r"\*{0,2}([\d.]+)\*{0,2}\s*\|\s*\*{0,2}([\d.]+)\*{0,2}\s*\|\s*\*{0,2}(\d+)\*{0,2}\s*\|"
)
_EVAL_ROW_RE = re.compile(
    r"^(deterministic|naive baseline)\s*:\s*recall=([\d.]+)\s+precision=([\d.]+)\s+clean_FP=(\d+)",
    re.MULTILINE,
)


def _readme_numbers() -> dict:
    text = README.read_text(encoding="utf-8")
    out = {}
    for label, recall, precision, fp in _README_ROW_RE.findall(text):
        key = "deterministic" if label.startswith("deterministic") else "naive"
        out[key] = (float(recall), float(precision), int(fp))
    return out


def _eval_numbers() -> dict:
    proc = subprocess.run(
        [sys.executable, str(EVAL_SCRIPT)],
        cwd=ROOT, capture_output=True, text=True,
    )
    if proc.returncode != 0:
        print(proc.stdout)
        print(proc.stderr, file=sys.stderr)
        raise SystemExit("eval/eval_redteam.py did not exit 0; cannot verify README numbers against it")
    out = {}
    for label, recall, precision, fp in _EVAL_ROW_RE.findall(proc.stdout):
        key = "deterministic" if label == "deterministic" else "naive"
        out[key] = (float(recall), float(precision), int(fp))
    return out


def main() -> int:
    readme = _readme_numbers()
    fresh = _eval_numbers()
    expected_keys = {"deterministic", "naive"}
    if set(readme) != expected_keys or set(fresh) != expected_keys:
        print(f"could not parse both head-to-head rows: readme={readme} eval={fresh}", file=sys.stderr)
        return 1

    ok = True
    for key in sorted(expected_keys):
        if readme[key] != fresh[key]:
            print(
                f"MISMATCH [{key}]: README says recall/precision/clean_FP={readme[key]}, "
                f"eval/eval_redteam.py says {fresh[key]}",
                file=sys.stderr,
            )
            ok = False

    if ok:
        print("OK: README head-to-head numbers match the fresh eval/eval_redteam.py output.")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
