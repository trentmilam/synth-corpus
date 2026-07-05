"""redteam-desk -- an AI decision red-team (advisor second-opinion).

Given a decision packet (an IC-memo recommendation + its supporting data room),
it adversarially surfaces integrity problems -- cross-document contradictions,
unsupported performance claims, and arithmetic errors -- each citation-gated, and
returns a risk verdict.

Design follows the validated FinGround-style blueprint (atomic claims -> verdict
{supported / contradicted / unverifiable} + formula reconstruction) and the
deep-research #1 recommendation: DETERMINISTIC verifiers over authoritative
documents, not a naive LLM-as-judge. Scored against synth-corpus's labeled
ground truth with independent detectors.
"""
from .verify import run_redteam, detect_contradictions, detect_unsupported_returns, detect_arithmetic

__all__ = ["run_redteam", "detect_contradictions", "detect_unsupported_returns", "detect_arithmetic"]
