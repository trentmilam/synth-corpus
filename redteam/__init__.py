"""redteam-desk -- an AI decision red-team (advisor second-opinion).

Given a decision packet (an IC-memo recommendation + its supporting data room),
it adversarially surfaces integrity problems -- cross-document contradictions,
unsupported performance claims, and arithmetic errors -- each citation-gated, and
returns a risk verdict.

Each claim resolves to a verdict (supported / contradicted / unverifiable),
with a reconstructed formula where applicable. A market/literature scan found
that deterministic verifiers over authoritative documents outperform a naive
LLM-as-judge for this task, so v1 is built that way. Scored against the
companion synth-corpus project's labeled ground truth with independent
detectors.
"""
from .verify import run_redteam, detect_contradictions, detect_unsupported_returns, detect_arithmetic

__all__ = ["run_redteam", "detect_contradictions", "detect_unsupported_returns", "detect_arithmetic"]
