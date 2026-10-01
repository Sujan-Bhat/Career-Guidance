"""LLM-generated self-assessment quizzes (Phase 7).

Generates quiz items per skill domain to refresh skill-assessment scores
(they feed the RL state and the career-prediction features).
"""
import json
import re

_DIFFICULTY_WORDS = {1: "basic", 2: "intermediate", 3: "advanced"}


def generate_quiz_items(skill: str, difficulty: int, n_items: int = 5, client=None) -> list[dict]:
    """Return [{"question", "options", "answer", "difficulty"}] with `answer`
    as the 0-based option index. Raises ValueError when the model output is
    not valid quiz JSON."""
    if client is None:
        from .client import get_client

        client = get_client()

    level = _DIFFICULTY_WORDS.get(int(difficulty), "intermediate")
    system = (
        "You write multiple-choice self-assessment quiz items for engineering students. "
        "Respond with ONLY a JSON array — no prose, no code fences. Each element must be "
        '{"question": str, "options": [str, ... 4 options ...], "answer": <0-based index>, '
        '"difficulty": <1|2|3>}.'
    )
    user = (
        f'Skill domain: "{skill}"\n'
        f"Difficulty: {level} ({int(difficulty)}/3)\n"
        f"Write exactly {int(n_items)} distinct multiple-choice items testing practical "
        "understanding of this skill at that level."
    )
    raw = client.complete(
        [{"role": "system", "content": system}, {"role": "user", "content": user}],
        temperature=0.7,
        max_tokens=1500,
    )
    return _parse_items(raw, n_items, difficulty)


def _close_truncated_array(fragment: str):
    """Best-effort repair of a JSON array cut off mid-element.

    Walks the fragment with depth/stack tracking, returns the list of complete
    top-level elements, or None when even the first element is incomplete."""
    depth = 0
    start = None
    complete = []
    in_str = False
    esc = False
    for i, ch in enumerate(fragment):
        if in_str:
            if esc:
                esc = False
            elif ch == "\\":
                esc = True
            elif ch == '"':
                in_str = False
            continue
        if ch == '"':
            in_str = True
        elif ch == "{":
            if depth == 0:
                start = i
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0 and start is not None:
                try:
                    complete.append(json.loads(fragment[start : i + 1]))
                except json.JSONDecodeError:
                    return None
                start = None
        elif ch == "]" and depth == 0:
            break
    return complete or None


def _parse_items(raw: str, n_items: int, difficulty: int) -> list[dict]:
    text = raw.strip()
    fence = re.search(r"```(?:json)?\s*(.*?)```", text, re.DOTALL)
    if fence:
        text = fence.group(1).strip()
    start, end = text.find("["), text.rfind("]")
    if start == -1 or end <= start:
        raise ValueError("LLM did not return a JSON array of quiz items")
    try:
        data = json.loads(text[start : end + 1])
    except json.JSONDecodeError as exc:
        # Thinking-era models can exhaust the output budget mid-array, leaving
        # the last element truncated. Salvage every COMPLETE element instead of
        # discarding the whole batch: close the array and drop the partial tail.
        salvaged = _close_truncated_array(text[start:])
        if salvaged is None:
            raise ValueError(f"LLM returned invalid quiz JSON: {exc}") from exc
        data = salvaged
    if not isinstance(data, list):
        raise ValueError("LLM quiz output must be a JSON array")

    items: list[dict] = []
    for entry in data:
        if not isinstance(entry, dict):
            continue
        question = str(entry.get("question") or "").strip()
        # Drop blank options, remembering where each survivor came from: the
        # model produced `answer` as an index into the ORIGINAL list, so
        # compacting first silently shifts the correct answer onto the wrong
        # option and the quiz grades the student incorrectly.
        kept = [
            (index, text)
            for index, text in enumerate(str(o) for o in (entry.get("options") or []))
            if text.strip()
        ]
        if not question or len(kept) < 2:
            continue
        remap = {original: compact for compact, (original, _text) in enumerate(kept)}
        options = [text.strip() for _original, text in kept]

        answer = entry.get("answer")
        if isinstance(answer, str) and len(answer.strip()) == 1 and answer.strip().upper() in "ABCDEFGH":
            answer = ord(answer.strip().upper()) - ord("A")  # letter -> index
        try:
            answer = int(answer)
        except (TypeError, ValueError):
            continue
        # original index -> compacted index; None when the answer pointed at a
        # blank option or outside the list entirely, so the item is discarded
        answer = remap.get(answer)
        if answer is None:
            continue
        try:
            item_difficulty = int(entry.get("difficulty", difficulty))
        except (TypeError, ValueError):
            item_difficulty = difficulty
        items.append(
            {
                "question": question,
                "options": options,
                "answer": answer,
                "difficulty": min(3, max(1, item_difficulty)),
            }
        )
        if len(items) >= n_items:
            break
    if not items:
        raise ValueError("LLM returned no usable quiz items")
    return items
