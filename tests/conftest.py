"""Ensure the repo root is importable so `import synthfin` works even if the
package has not been `pip install -e .`'d yet -- mirrors the sys.path trick
already used by `run_demo.py` / `eval/eval.py`.
"""
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)
