"""synth-corpus demo: generate a clean corpus and a flawed one, write them to out/,
and print a summary + the answer key.

    python run_demo.py
"""
import json
import os
import sys

ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ROOT)

from synthfin.generate import generate            # noqa: E402
from synthfin.check import check_consistency       # noqa: E402
from synthfin.world import build_world             # noqa: E402

SEED = 20260704


def write_corpus(corpus, subdir):
    base = os.path.join(ROOT, "out", subdir)
    os.makedirs(base, exist_ok=True)
    for name, text in corpus.docs.items():
        with open(os.path.join(base, f"{name}.md"), "w", encoding="utf-8") as f:
            f.write(text)
    with open(os.path.join(base, "manifest.json"), "w", encoding="utf-8") as f:
        json.dump(corpus.manifest, f, indent=2)
    return base


def main() -> int:
    world = build_world(SEED)
    print(f"World: {world.fund_name} / LP {world.lp_name}")
    print(f"  fund size {world.committed_capital:,.0f}  mgmt {world.mgmt_fee_pct}%  carry {world.carry_pct}%")
    print(f"  LP commit {world.lp_commitment:,.0f}  contrib {world.contributions:,.0f}  "
          f"dist {world.distributions:,.0f}  ending NAV {world.ending_nav:,.0f}  TVPI {world.tvpi:.2f}x")

    clean = generate(SEED)
    base = write_corpus(clean, "clean")
    print(f"\nCLEAN corpus -> {base}  ({len(clean.docs)} docs)")
    print(f"  consistency findings: {len(check_consistency(clean.docs, world))}  (expect 0)")

    injects = [
        {"type": "contradiction", "doc": "ddq", "field": "management_fee"},
        {"type": "ungrounded_claim"},
        {"type": "arithmetic_error"},
    ]
    flawed = generate(SEED, injects=injects)
    base = write_corpus(flawed, "flawed")
    findings = check_consistency(flawed.docs, world)
    print(f"\nFLAWED corpus -> {base}  ({len(flawed.manifest['flaws'])} injected flaws)")
    print("  answer key:")
    for f in flawed.manifest["flaws"]:
        print(f"    - {f['type']:16} doc={f['doc']:16} field={f['field']}")
    print("  checker findings:")
    for f in findings:
        print(f"    - {f['type']:16} doc={f['doc']:16} field={f['field']}")
    print("  (the ungrounded_claim is in the answer key but not a structural finding -- "
          "it needs a red-team, which is exactly what this harness will score.)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
