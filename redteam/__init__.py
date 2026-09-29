"""redteam: an AI decision red-team (advisor second-opinion).

Given a decision packet (an IC-memo recommendation + its supporting data room),
it adversarially surfaces integrity problems: cross-document contradictions,
unsupported performance claims, and arithmetic errors, each citation-gated, and
returns a risk verdict.

Each claim resolves to a verdict (supported / contradicted / unverifiable),
with a reconstructed formula where applicable. Deterministic verifiers over
authoritative documents are a better fit here than a naive LLM-as-judge,
because out-of-the-box LLMs are unreliable citation verifiers. Scored against
synth-corpus's labeled ground truth with independent detectors.
"""
from .verify import run_redteam, detect_contradictions, detect_unsupported_returns, detect_arithmetic

__all__ = ["run_redteam", "detect_contradictions", "detect_unsupported_returns", "detect_arithmetic"]
