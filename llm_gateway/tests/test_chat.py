"""GuidanceChat tests — fake client, no network (Phase 7)."""
import pytest

from careermind_llm.chat import SYSTEM_PROMPT, GuidanceChat, build_context


class FakeClient:
    def __init__(self, reply="Let's explore options.", fail=False, empty=False):
        self.reply = "" if empty else reply
        self.fail = fail
        self.calls = []

    def complete(self, messages, **kwargs):
        self.calls.append(messages)
        if self.fail:
            raise RuntimeError("provider down")
        return self.reply


def test_build_context_renders_block():
    ctx = build_context(
        {"programme": "BE CSE", "year_of_study": 3, "grades": {"Physics": 78.5},
         "skills": {"python": 90, "sql": 70}},
        {"score": 0.72, "trend": 0.61},
        [{"name": "Software Engineering", "decision": "accepted"}],
    )
    assert "BE CSE" in ctx and "year 3" in ctx
    assert "Physics 78.5" in ctx
    assert "python 90" in ctx and "sql 70" in ctx
    assert "(FES): 0.72" in ctx and "improving" in ctx
    assert "Software Engineering (accepted)" in ctx


def test_build_context_handles_empty():
    assert build_context({}, None, []) == ""


def test_chat_grounds_system_prompt_and_context():
    fake = FakeClient()
    chat = GuidanceChat(fake)
    reply = chat.chat("s1", "what should I do?", context="FES: 0.7")
    assert reply == "Let's explore options."
    first = fake.calls[0]
    assert first[0]["role"] == "system"
    system = first[0]["content"]
    assert "never tell the student" in system  # agency-preserving principle
    assert "FES: 0.7" in system  # grounding context
    assert first[-1] == {"role": "user", "content": "what should I do?"}


def test_chat_keeps_multi_turn_history():
    fake = FakeClient()
    chat = GuidanceChat(fake)
    chat.chat("s1", "first")
    chat.chat("s1", "second")
    roles = [m["role"] for m in fake.calls[1]]
    assert roles == ["system", "user", "assistant", "user"]


def test_history_window_trims_and_isolates_students():
    fake = FakeClient()
    chat = GuidanceChat(fake, history_limit=2)
    for i in range(5):
        chat.chat("s1", f"turn {i}")
    assert len(chat._history["s1"]) <= 4  # 2 * history_limit
    chat.chat("s2", "hello")
    assert [m["content"] for m in chat._history["s2"]] == ["hello", fake.reply]
    assert all("turn" not in m["content"] for m in chat._history["s2"])


def test_client_failure_does_not_keep_user_turn():
    fake = FakeClient(fail=True)
    chat = GuidanceChat(fake)
    with pytest.raises(RuntimeError, match="provider down"):
        chat.chat("s1", "hi")
    assert chat._history["s1"] == []


def test_empty_reply_raises_and_reverts():
    fake = FakeClient(empty=True)
    chat = GuidanceChat(fake)
    with pytest.raises(RuntimeError, match="empty response"):
        chat.chat("s1", "hi")
    assert chat._history["s1"] == []


def test_system_prompt_is_agency_preserving():
    assert "never tell the student which career they 'should' choose" in SYSTEM_PROMPT
