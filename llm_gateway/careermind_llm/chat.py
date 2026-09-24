"""Conversational career guidance (Part A, Phase 7).

Grounds the LLM with student context (FES, profile, current recommendations)
and enforces the agency-preserving guidance principle of Niles and
Harris-Bowlsbey [26]: the assistant may explore, inform, and challenge —
never issue deterministic career verdicts.
"""

SYSTEM_PROMPT = (
    "You are CAREERMIND, a career guidance assistant for engineering students. "
    "Use the provided student context (Focus Efficiency Score, academic records, "
    "skills, current recommendations) to ground your answers. "
    "Preserve student agency: present options, trade-offs, and questions to reflect on; "
    "never tell the student which career they 'should' choose."
)


def build_context(profile: dict, fes: dict, recommendations: list) -> str:
    """Phase 7: render student context as a compact grounding block."""
    raise NotImplementedError("Phase 7")


class GuidanceChat:
    """Phase 7: multi-turn chat via LLMClient.complete() with the
    agency-preserving system prompt; per-student history window."""

    def __init__(self, client):
        self.client = client

    def chat(self, student_id: str, user_message: str) -> str:
        raise NotImplementedError("Phase 7")
