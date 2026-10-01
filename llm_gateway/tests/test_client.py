"""Client factory + adapter tests — no provider SDK required (lazy imports)."""
import sys
import types

import pytest

from careermind_llm.client import GEMINI_THINKING_HEADROOM, PROVIDERS, get_client
from careermind_llm.client import AnthropicClient, GeminiClient, OpenAIClient

MESSAGES = [
    {"role": "system", "content": "Be helpful."},
    {"role": "user", "content": "Hello"},
]


def test_factory_returns_provider_adapters():
    assert isinstance(get_client("openai", api_key="k", model="m"), OpenAIClient)
    assert isinstance(get_client("anthropic", api_key="k", model="m"), AnthropicClient)
    assert isinstance(get_client("gemini", api_key="k", model="m"), GeminiClient)


def test_factory_rejects_unknown_provider(monkeypatch):
    monkeypatch.delenv("LLM_PROVIDER", raising=False)
    with pytest.raises(ValueError, match="Unknown LLM provider"):
        get_client("not-a-provider")


def test_providers_tuple():
    assert PROVIDERS == ("openai", "anthropic", "gemini")


def test_adapters_raise_without_api_key():
    for cls in (OpenAIClient, AnthropicClient, GeminiClient):
        with pytest.raises(RuntimeError, match="LLM_API_KEY"):
            cls(api_key="", model="m").complete(MESSAGES)


def test_openai_adapter_completes(monkeypatch):
    captured = {}

    class _Completions:
        def create(self, **kwargs):
            captured.update(kwargs)
            return types.SimpleNamespace(
                choices=[types.SimpleNamespace(message=types.SimpleNamespace(content="  hi  "))]
            )

    module = types.ModuleType("openai")

    def _openai(api_key=None):
        captured["api_key"] = api_key
        return types.SimpleNamespace(chat=types.SimpleNamespace(completions=_Completions()))

    module.OpenAI = _openai
    monkeypatch.setitem(sys.modules, "openai", module)

    client = OpenAIClient(api_key="sk-test", model="gpt-4o-mini")
    assert client.complete(MESSAGES) == "hi"
    assert captured["api_key"] == "sk-test"
    assert captured["model"] == "gpt-4o-mini"
    assert captured["messages"] == MESSAGES


def test_anthropic_adapter_lifts_system_prompt(monkeypatch):
    captured = {}

    class _Messages:
        def create(self, **kwargs):
            captured.update(kwargs)
            return types.SimpleNamespace(
                content=[
                    types.SimpleNamespace(type="text", text="part one "),
                    types.SimpleNamespace(type="text", text="part two"),
                ]
            )

    module = types.ModuleType("anthropic")
    module.Anthropic = lambda api_key=None: types.SimpleNamespace(messages=_Messages())
    monkeypatch.setitem(sys.modules, "anthropic", module)

    client = AnthropicClient(api_key="sk-ant", model="claude-x")
    assert client.complete(MESSAGES) == "part one part two"
    assert captured["system"] == "Be helpful."
    assert captured["messages"] == [{"role": "user", "content": "Hello"}]  # system stripped
    assert captured["model"] == "claude-x"


def test_gemini_adapter_flattens_chat(monkeypatch):
    captured = {}
    module = types.ModuleType("google.generativeai")
    module.configure = lambda api_key=None: captured.setdefault("api_key", api_key)

    class _Model:
        def __init__(self, model_name, system_instruction=None):
            captured["model"] = model_name
            captured["system_instruction"] = system_instruction

        def generate_content(self, parts, generation_config=None):
            captured["parts"] = parts
            captured["config"] = generation_config
            return types.SimpleNamespace(text=" grounded ")

    module.GenerativeModel = _Model
    package = types.ModuleType("google")
    package.generativeai = module
    monkeypatch.setitem(sys.modules, "google", package)
    monkeypatch.setitem(sys.modules, "google.generativeai", module)

    client = GeminiClient(api_key="g-key", model="")
    assert client.complete(MESSAGES) == "grounded"
    assert captured["api_key"] == "g-key"
    assert captured["system_instruction"] == "Be helpful."
    assert captured["parts"] == ["Student: Hello"]
    # visible-budget contract: the caller's cap plus the thinking headroom
    assert captured["config"]["max_output_tokens"] == 1024 + GEMINI_THINKING_HEADROOM
