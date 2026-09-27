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


def build_context(profile: dict, fes: dict | None, recommendations: list) -> str:
    """Render student context as a compact grounding block."""
    lines = []

    name_bits = []
    if profile.get("programme"):
        name_bits.append(profile["programme"])
    if profile.get("year_of_study"):
        name_bits.append(f"year {profile['year_of_study']}")
    if name_bits:
        lines.append(f"Programme: {', '.join(name_bits)}")

    grades = profile.get("grades") or {}
    if grades:
        lines.append(
            "Grades: " + ", ".join(f"{subject} {grade:g}" for subject, grade in sorted(grades.items()))
        )

    skills = sorted((profile.get("skills") or {}).items(), key=lambda kv: kv[1], reverse=True)[:5]
    if skills:
        lines.append(
            "Self-assessed skills (0-100): " + ", ".join(f"{skill} {score:g}" for skill, score in skills)
        )

    if fes and fes.get("score") is not None:
        line = f"Focus Efficiency Score (FES): {fes['score']:.2f} of 1.0"
        trend = fes.get("trend")
        if trend is not None:
            direction = "improving" if trend > 0.55 else "declining" if trend < 0.45 else "stable"
            line += f", trend {direction}"
        lines.append(line)

    if recommendations:
        rendered = ", ".join(
            f"{rec.get('name') or rec.get('item_id')} ({rec.get('decision', 'pending')})"
            for rec in recommendations[:5]
        )
        lines.append(f"Current pathway recommendations: {rendered}")

    return "\n".join(lines)


class GuidanceChat:
    """Multi-turn chat via LLMClient.complete() with the agency-preserving
    system prompt; per-student history window."""

    def __init__(self, client, history_limit: int = 12):
        self.client = client
        self.history_limit = history_limit
        self._history: dict[str, list[dict]] = {}

    def chat(self, student_id: str, user_message: str, context: str | None = None) -> str:
        history = self._history.setdefault(student_id, [])
        history.append({"role": "user", "content": user_message})

        system = SYSTEM_PROMPT
        if context:
            system += f"\n\nStudent context:\n{context}"
        messages = [{"role": "system", "content": system}, *history[-self.history_limit :]]

        try:
            reply = self.client.complete(messages, temperature=0.6, max_tokens=600)
        except Exception:
            history.pop()  # don't keep a turn the model never saw
            raise
        if not reply:
            history.pop()
            raise RuntimeError("LLM returned an empty response")

        history.append({"role": "assistant", "content": reply})
        overflow = len(history) - 2 * self.history_limit
        if overflow > 0:
            del history[:overflow]
        return reply
