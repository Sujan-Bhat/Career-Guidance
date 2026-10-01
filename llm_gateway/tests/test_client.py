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


# ---------------------------------------------------------------------------
# Gemini model failover: 429 quota / 404 retired models walk the fallback chain
# ---------------------------------------------------------------------------


class _ResourceExhausted(Exception):
    """Mirrors google.api_core.exceptions.ResourceExhausted (429 quota)."""


class _NotFound(Exception):
    """Mirrors google.api_core.exceptions.NotFound (404 model unavailable)."""


def _install_fake_gemini(monkeypatch, outcomes):
    """Fake google.generativeai + google.api_core.exceptions.

    `outcomes` maps model name -> text to return or exception to raise; the
    captured call order lets tests assert exactly which models were tried.
    """
    captured = {"calls": []}
    module = types.ModuleType("google.generativeai")
    module.configure = lambda api_key=None: None

    exceptions = types.ModuleType("google.api_core.exceptions")
    exceptions.ResourceExhausted = _ResourceExhausted
    exceptions.NotFound = _NotFound
    api_core = types.ModuleType("google.api_core")
    api_core.exceptions = exceptions

    class _Model:
        def __init__(self, model_name, system_instruction=None):
            self.model_name = model_name

        def generate_content(self, parts, generation_config=None):
            captured["calls"].append(self.model_name)
            outcome = outcomes[self.model_name]
            if isinstance(outcome, Exception):
                raise outcome
            return types.SimpleNamespace(text=outcome)

    module.GenerativeModel = _Model
    package = types.ModuleType("google")
    package.generativeai = module
    package.api_core = api_core
    monkeypatch.setitem(sys.modules, "google", package)
    monkeypatch.setitem(sys.modules, "google.generativeai", module)
    monkeypatch.setitem(sys.modules, "google.api_core", api_core)
    monkeypatch.setitem(sys.modules, "google.api_core.exceptions", exceptions)
    return captured


def test_quota_error_fails_over_to_fallback_model(monkeypatch):
    """A 429 on the primary must not reach the caller while a fallback can
    answer — daily quota is a per-model bucket, so the next model can."""
    captured = _install_fake_gemini(
        monkeypatch,
        {
            "gemini-primary": _ResourceExhausted("429 quota exceeded"),
            "gemini-fallback": "  answer  ",
        },
    )
    monkeypatch.setenv("LLM_FALLBACK_MODELS", "gemini-fallback")

    client = GeminiClient(api_key="k", model="gemini-primary")
    assert client.complete(MESSAGES) == "answer"
    assert captured["calls"] == ["gemini-primary", "gemini-fallback"]


def test_retired_model_fails_over_too(monkeypatch):
    """Google retires models outright (the gemini-2.5-flash case); a 404 on
    the primary is equally environmental and must fail over."""
    captured = _install_fake_gemini(
        monkeypatch,
        {
            "gemini-retired": _NotFound("models/gemini-retired is not found"),
            "gemini-fallback": "ok",
        },
    )
    monkeypatch.setenv("LLM_FALLBACK_MODELS", "gemini-fallback")

    client = GeminiClient(api_key="k", model="gemini-retired")
    assert client.complete(MESSAGES) == "ok"
    assert captured["calls"] == ["gemini-retired", "gemini-fallback"]


def test_unrelated_errors_surface_immediately(monkeypatch):
    """A malformed request (or bad key) is NOT a model problem — failing over
    would hide the bug behind whichever model answers next."""
    captured = _install_fake_gemini(
        monkeypatch, {"gemini-primary": ValueError("invalid request payload")}
    )
    monkeypatch.setenv("LLM_FALLBACK_MODELS", "gemini-fallback")

    client = GeminiClient(api_key="k", model="gemini-primary")
    with pytest.raises(ValueError, match="invalid request payload"):
        client.complete(MESSAGES)
    assert captured["calls"] == ["gemini-primary"]  # single attempt, no failover


def test_all_candidates_exhausted_raises_last_error(monkeypatch):
    """When every model is out of quota the real 429 propagates, so callers
    keep their existing 502 handling instead of seeing a synthetic error."""
    captured = _install_fake_gemini(
        monkeypatch,
        {
            "gemini-a": _ResourceExhausted("primary quota gone"),
            "gemini-b": _ResourceExhausted("fallback quota gone"),
        },
    )
    monkeypatch.setenv("LLM_FALLBACK_MODELS", "gemini-b")

    client = GeminiClient(api_key="k", model="gemini-a")
    with pytest.raises(_ResourceExhausted, match="fallback quota gone"):
        client.complete(MESSAGES)
    assert captured["calls"] == ["gemini-a", "gemini-b"]


def test_model_chain_parsing_and_dedup(monkeypatch):
    """Whitespace-tolerant, order-preserving, duplicates dropped."""
    monkeypatch.setenv("LLM_FALLBACK_MODELS", " gemini-b , gemini-a , gemini-b,,")
    assert GeminiClient(api_key="k", model="gemini-a").models == ["gemini-a", "gemini-b"]
    assert GeminiClient(api_key="k", model="gemini-b").models == ["gemini-b", "gemini-a"]


def test_model_chain_without_fallbacks_is_single_model(monkeypatch):
    """No LLM_FALLBACK_MODELS -> exactly the pre-failover behaviour."""
    monkeypatch.delenv("LLM_FALLBACK_MODELS", raising=False)
    assert GeminiClient(api_key="k", model="gemini-only").models == ["gemini-only"]
    assert GeminiClient(api_key="k", model="").models == ["gemini-1.5-flash"]


def test_factory_wires_env_fallbacks(monkeypatch):
    """get_client(...) must pick up the env fallback list — quizgen, explain
    and chat all build their clients through the factory."""
    monkeypatch.setenv("LLM_FALLBACK_MODELS", "gemini-b")
    client = get_client("gemini", api_key="k", model="gemini-a")
    assert client.models == ["gemini-a", "gemini-b"]
