"""Console-script entry points (see `pyproject.toml`'s `[project.scripts]`).

Thin wrappers around the repo-root `run_demo.py` / `eval/eval.py` scripts so
`pip install -e .` gives an installed CLI verb (`synthfin-demo`, `synthfin-eval`)
instead of requiring the caller to know to run those scripts from inside the
checkout. Loads each script by file path rather than duplicating its logic, so
there is exactly one copy of the demo/eval behavior.
"""
from __future__ import annotations

import importlib.util
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent


def _run_script(rel_path: str) -> int:
    path = _ROOT / rel_path
    spec = importlib.util.spec_from_file_location(f"_synthfin_script_{path.stem}", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.main()


def demo_main() -> int:
    return _run_script("run_demo.py")


def eval_main() -> int:
    return _run_script("eval/eval.py")
