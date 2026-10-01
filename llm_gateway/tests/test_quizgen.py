"""Quiz generation + explanation tests — fake client, no network (Phase 7)."""
import json

import pytest

from careermind_llm.explain import generate_explanation
from careermind_llm.quizgen import generate_quiz_items


class FakeClient:
    def __init__(self, reply):
        self.reply = reply
        self.calls = []

    def complete(self, messages, **kwargs):
        self.calls.append(messages)
        return self.reply


def _items(n=3, answer=1):
    return [
        {"question": f"Question {i}?", "options": ["a", "b", "c", "d"], "answer": answer, "difficulty": 2}
        for i in range(n)
    ]


def test_quiz_parses_plain_json_and_truncates():
    fake = FakeClient(json.dumps(_items(4)))
    items = generate_quiz_items("python", 2, n_items=2, client=fake)
    assert len(items) == 2
    assert set(items[0]) == {"question", "options", "answer", "difficulty"}
    assert items[0]["answer"] == 1


def test_quiz_parses_fenced_json_with_letter_answer():
    raw = '```json\n[{"question": "Q?", "options": ["x", "y", "z", "w"], "answer": "C", "difficulty": 2}]\n```'
    items = generate_quiz_items("sql", 2, n_items=1, client=FakeClient(raw))
    assert items[0]["answer"] == 2  # C -> index 2


def test_quiz_prompt_contains_skill_and_difficulty():
    fake = FakeClient(json.dumps(_items(1)))
    generate_quiz_items("embedded systems", 3, n_items=1, client=fake)
    user = fake.calls[0][1]["content"]
    assert "embedded systems" in user and "advanced" in user
    assert fake.calls[0][0]["role"] == "system"
    assert "JSON" in fake.calls[0][0]["content"]


def test_quiz_skips_malformed_entries():
    raw = json.dumps(
        [
            {"question": "ok?", "options": ["a", "b"], "answer": 1},
            {"question": "", "options": ["a", "b"], "answer": 0},  # no question
            {"question": "bad", "options": ["a"], "answer": 0},  # too few options
            {"question": "bad idx", "options": ["a", "b"], "answer": 5},  # out of range
            {"question": "fine?", "options": ["a", "b", "c"], "answer": 2},
        ]
    )
    items = generate_quiz_items("java", 2, n_items=5, client=FakeClient(raw))
    assert [i["question"] for i in items] == ["ok?", "fine?"]


def test_quiz_rejects_non_json_output():
    with pytest.raises(ValueError, match="JSON array"):
        generate_quiz_items("python", 2, client=FakeClient("I cannot produce that."))
    with pytest.raises(ValueError, match="no usable quiz items"):
        generate_quiz_items(
            "python", 2, client=FakeClient('[{"question": "q", "options": [], "answer": 0}]')
        )


def test_explanation_cites_provenance_and_features():
    fake = FakeClient("This pathway surfaced because your ML skill is strong.")
    text = generate_explanation(
        {
            "name": "Data Science",
            "category": "data",
            "stage1_eligible": True,
            "stage2_cf_score": 0.41,
            "stage3_fm_score": 0.83,
        },
        [{"feature": "skill_ml_fundamentals", "value": 90}],
        client=fake,
    )
    assert text.startswith("This pathway")
    user = fake.calls[0][1]["content"]
    assert "Data Science" in user and "0.83" in user
    assert "skill_ml_fundamentals=90" in user
    assert "agency" in fake.calls[0][0]["content"].lower() or "verdict" in fake.calls[0][0]["content"].lower()


def test_explanation_rejects_empty_reply():
    with pytest.raises(ValueError, match="empty explanation"):
        generate_explanation({"item_id": "c01"}, [], client=FakeClient("  "))


def test_blank_option_does_not_shift_the_answer_index():
    """Compacting the option list must remap `answer`, otherwise dropping a
    blank option regrades the item: the model's index 2 ("D") would become
    index 2 in a 3-option list ("C"), so the student is marked wrong."""
    raw = json.dumps(
        [
            {"question": "Pick one", "options": ["A", "", "C", "D"], "answer": 2,
             "difficulty": 2},
        ]
    )
    items = generate_quiz_items("java", 2, n_items=1, client=FakeClient(raw))
    assert len(items) == 1
    assert items[0]["options"] == ["A", "C", "D"]
    assert items[0]["options"][items[0]["answer"]] == "C"


def test_letter_answer_survives_option_compaction():
    raw = json.dumps(
        [{"question": "Pick", "options": ["", "X", "Y"], "answer": "C", "difficulty": 1}]
    )
    items = generate_quiz_items("java", 1, n_items=1, client=FakeClient(raw))
    assert items[0]["options"] == ["X", "Y"]
    assert items[0]["options"][items[0]["answer"]] == "Y"  # C -> index 2 -> "Y"


def test_answer_pointing_at_a_blank_option_is_dropped():
    raw = json.dumps(
        [
            {"question": "skip me", "options": ["A", "", "C"], "answer": 1, "difficulty": 1},
            {"question": "keep me", "options": ["A", "B", "C"], "answer": 1, "difficulty": 1},
        ]
    )
    items = generate_quiz_items("java", 1, n_items=2, client=FakeClient(raw))
    assert [i["question"] for i in items] == ["keep me"]

def test_quiz_salvages_complete_items_from_truncated_array():
    # thinking-era models can cut the output mid-array; the complete elements
    # must survive instead of the whole batch being discarded
    raw = json.dumps(_items(3))[:-40]  # cut inside the last element
    items = generate_quiz_items("python", 2, n_items=5, client=FakeClient(raw))
    assert len(items) == 2
    assert items[0]["answer"] == 1


def test_quiz_salvage_ignores_brackets_inside_strings():
    raw = (
        '[{"question": "Has [brackets] and {braces}?", "options": ["a", "b"], "answer": 0, "difficulty": 2}, '
        '{"question": "Trunc'
    )
    items = generate_quiz_items("dsa", 2, n_items=5, client=FakeClient(raw))
    assert len(items) == 1
    assert items[0]["question"] == "Has [brackets] and {braces}?"


def test_quiz_salvage_handles_escaped_quotes():
    raw = (
        '[{"question": "What does \\"float\\" mean?", "options": ["a", "b"], "answer": 1, "difficulty": 2}, '
        '{"question": "Cut'
    )
    items = generate_quiz_items("java", 2, n_items=5, client=FakeClient(raw))
    assert len(items) == 1
    assert items[0]["question"] == 'What does "float" mean?'


def test_quiz_raises_when_first_element_is_truncated():
    # a ] inside a string value defeats the rfind guard, json.loads fails,
    # and no complete element exists -> salvage returns None -> ValueError
    raw = '[{"question": "has ] bracket", "options": ["a"'
    with pytest.raises(ValueError, match="invalid quiz JSON"):
        generate_quiz_items("python", 2, n_items=5, client=FakeClient(raw))
