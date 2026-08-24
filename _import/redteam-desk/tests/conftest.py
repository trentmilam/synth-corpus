"""Make `redteam` importable when running `pytest` directly from the repo
root without an editable install (`pip install -e .`) -- pytest's default
"prepend" import mode only puts the `tests/` directory itself on sys.path,
not its parent, since there is no `tests/__init__.py`."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
