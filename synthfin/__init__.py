"""synthfin -- synthetic financial corpus generator (labeled test-harness).

Renders a coherent set of wealth-manager alternatives-diligence documents (PPM,
LPA, DDQ, ADV, K-1, capital-account statement, IC memo) from ONE seeded world
state, so every cross-document figure ties out. A flaw-injection layer plants
labeled defects, producing a ground-truth manifest downstream tools score against.
Deterministic + offline.
"""
from .world import World, build_world
from .generate import Corpus, generate
from .check import check_consistency, detect_worldfree, detect_naive

__all__ = ["World", "build_world", "Corpus", "generate", "check_consistency",
           "detect_worldfree", "detect_naive"]
