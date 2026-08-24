"""redteam-desk demo: generate a flawed decision packet with synth-corpus, run the
red-team, print the report, and score it against the labeled answer key.

This is the FULL REPRODUCTION path and requires the companion `synth-corpus`
repo cloned as a sibling directory (see README "Full reproduction"):

    git clone https://github.com/trentmilam/synth-corpus ../synth-corpus
    python run_demo.py

For a zero-dependency example that needs nothing but this repo, see the
README Quickstart (calls `redteam.verify.run_redteam` directly on an inline
`docs` dict).
"""
import os
import sys

ROOT = os.path.dirname(os.path.abspath(__file__))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from redteam.verify import run_redteam             # noqa: E402
from synthfin.generate import generate             # noqa: E402

SEED = 12345
_MAP = {"contradiction": "contradiction", "ungrounded_claim": "unsupported_claim", "arithmetic_error": "arithmetic"}


def main() -> int:
    injects = [
        {"type": "contradiction", "doc": "ddq", "field": "management_fee"},
        {"type": "ungrounded_claim"},
        {"type": "arithmetic_error"},
    ]
    corpus = generate(SEED, injects=injects)
    report = run_redteam(corpus)

    print(f"Decision packet: {corpus.manifest['world']['fund_name']}")
    print(f"RED-TEAM VERDICT: {report['verdict'].upper()}\n")
    print("Findings (each citation-gated):")
    for f in report["findings"]:
        print(f"  [{f['type']}] {f['detail']}")
        print(f"        -> {f['citation']}")

    # score vs the labeled answer key
    planted = corpus.manifest["flaws"]
    found_types_by_doc = {(f["type"], f["doc"]) for f in report["findings"]}
    hits = sum(1 for p in planted if (_MAP[p["type"]], p["doc"]) in found_types_by_doc)
    print(f"\nScore vs answer key: recall {hits}/{len(planted)} planted flaws caught; "
          f"{len(report['findings'])} findings total.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
