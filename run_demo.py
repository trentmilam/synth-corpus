"""redteam-desk demo: generate a flawed decision packet with synth-corpus, run the
red-team, print the report, and score it against the labeled answer key.

    python run_demo.py
"""
import os
import sys

REDTEAM_ROOT = os.path.dirname(os.path.abspath(__file__))
SYNTH = os.path.join(os.path.dirname(REDTEAM_ROOT), "synth-corpus")
sys.path.insert(0, REDTEAM_ROOT)
sys.path.insert(0, SYNTH)

from redteam.verify import run_redteam            # noqa: E402
from synthfin.generate import generate            # noqa: E402

SEED = 20260704
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
