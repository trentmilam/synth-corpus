"""pytest-discoverable wrapper around `eval/eval.py` and `run_demo.py`.

`eval/eval.py` is the canonical, hand-rolled harness (exit-code + print
asserts; currently 35 checks across a 201-seed sweep) -- this file makes it
visible to `pytest -k`, `coverage.py`, and IDE test runners without
duplicating its logic.
"""
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def test_eval_harness_passes():
    result = subprocess.run(
        [sys.executable, str(ROOT / "eval" / "eval.py")],
        cwd=ROOT, capture_output=True, text=True,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert "RESULT: PASS" in result.stdout


def test_run_demo_passes():
    result = subprocess.run(
        [sys.executable, str(ROOT / "run_demo.py")],
        cwd=ROOT, capture_output=True, text=True,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert "CLEAN corpus" in result.stdout
    assert "FLAWED corpus" in result.stdout
