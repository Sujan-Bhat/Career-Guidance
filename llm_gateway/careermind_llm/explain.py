"""Plain-language recommendation explanations (NFR07, Phase 7).

Input: a recommendation with per-stage cascade provenance + contributing
profile features (including FES). Output: a short, non-technical explanation
of WHY the item was recommended to THIS student.
"""

_SYSTEM = (
    "You explain CAREERMIND career recommendations in plain language for "
    "engineering students. Given the cascade provenance (knowledge-graph "
    "eligibility, collaborative-filtering affinity, factorisation-machine "
    "score) and the student's top contributing features, write 1-2 sentences "
    "(max 60 words) saying WHY this pathway was surfaced FOR THIS student. "
    "Be specific and non-technical. Preserve agency: frame it as a reason to "
    "explore the pathway, not a verdict about the student's career."
)


def generate_explanation(recommendation: dict, contributing_features: list[dict], client=None) -> str:
    """Prompt the LLM with the recommendation's Stage 1-3 provenance
    (KG eligibility, CF affinity, FM score) and top features; return the
    explanation string to store on the Recommendation document."""
    if client is None:
        from .client import get_client

        client = get_client()

    provenance = (
        f"Pathway: {recommendation.get('name') or recommendation.get('item_id')} "
        f"(category: {recommendation.get('category', 'unknown')})\n"
        f"Stage 1 knowledge-graph eligibility: {recommendation.get('stage1_eligible')}\n"
        f"Stage 2 collaborative-filtering score: {recommendation.get('stage2_cf_score')}\n"
        f"Stage 3 factorisation-machine score: {recommendation.get('stage3_fm_score')}"
    )
    features = ", ".join(
        f"{row.get('feature')}={row.get('value')}"
        for row in (contributing_features or [])[:6]
        if isinstance(row, dict)
    ) or "none recorded"
    user = f"{provenance}\nTop contributing student features: {features}"

    reply = client.complete(
        [{"role": "system", "content": _SYSTEM}, {"role": "user", "content": user}],
        temperature=0.4,
        max_tokens=220,
    )
    if not reply or not reply.strip():
        raise ValueError("LLM returned an empty explanation")
    return reply.strip()
