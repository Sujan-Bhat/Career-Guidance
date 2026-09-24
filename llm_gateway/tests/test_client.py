"""Client factory tests — no provider SDK required (lazy imports)."""
import pytest

from careermind_llm.client import PROVIDERS, get_client
from careermind_llm.client import AnthropicClient, GeminiClient, OpenAIClient


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
