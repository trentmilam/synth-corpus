"""Shared bootstrap for scripts that need the companion synth-corpus repo
(`eval/eval.py`, `run_demo.py`): resolves the sibling checkout, verifies its
identity, and raises one clear error message (pointing at the real README
section) if it's missing -- instead of duplicating this ~20-line block in
every script that needs it.
"""
from __future__ import annotations

import os
import sys


def _assert_synthfin_identity(mod) -> None:
    """Fail loudly if whatever landed in ../synth-corpus isn't the expected
    package -- it is resolved by relative disk position, not a pinned or
    verified install, so it gets no benefit of the doubt."""
    doc = mod.__doc__ or ""
    if "synthetic financial corpus generator" not in doc or not hasattr(mod, "generate"):
        raise RuntimeError(
            "the 'synthfin' module found on sys.path does not match the expected "
            "companion synth-corpus package (identity check failed) -- refusing "
            "to run against an unverified sibling directory"
        )


def bootstrap_synth_corpus(redteam_root: str):
    """Put `redteam_root` (this repo) and its `../synth-corpus` sibling on
    sys.path -- appended, never prepended: a sibling directory resolved
    purely by relative disk position must never get import priority over
    anything already trusted on the path -- then import and identity-check
    the `synthfin` package.

    Returns `(synthfin, generate)`. Raises `RuntimeError` with a clear
    message if the sibling repo isn't present or doesn't match the expected
    companion package.
    """
    synth = os.path.join(os.path.dirname(redteam_root), "synth-corpus")
    sys.path.append(redteam_root)
    sys.path.append(synth)

    try:
        import synthfin
        from synthfin.generate import generate
    except ImportError as exc:
        raise RuntimeError(
            "clone synth-corpus as a sibling directory: see README "
            "'Full reproduction (requires the companion synth-corpus repo)'"
        ) from exc

    _assert_synthfin_identity(synthfin)
    return synthfin, generate
