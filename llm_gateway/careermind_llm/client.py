"""Provider-agnostic LLM client (Part A).

One interface, three adapters (OpenAI / Anthropic / Gemini). SDK imports are
lazy so the package installs without any provider SDK; keys are read from the
environment (LLM_PROVIDER, LLM_API_KEY, LLM_MODEL) with per-call overrides.
"""
import os
from abc import ABC, abstractmethod

PROVIDERS = ("openai", "anthropic", "gemini")


class LLMClient(ABC):
    """Minimal chat-completion interface shared by all providers."""

    @abstractmethod
    def complete(self, messages: list[dict], temperature: float = 0.7, max_tokens: int = 1024) -> str:
        """`messages`: [{"role": "system"|"user"|"assistant", "content": str}]."""


class OpenAIClient(LLMClient):
    def __init__(self, api_key: str, model: str):
        self.api_key = api_key
        self.model = model

    def complete(self, messages, temperature=0.7, max_tokens=1024) -> str:
        """Phase 7: lazy `import openai` + chat.completions.create(...)."""
        raise NotImplementedError("Phase 7")


class AnthropicClient(LLMClient):
    def __init__(self, api_key: str, model: str):
        self.api_key = api_key
        self.model = model

    def complete(self, messages, temperature=0.7, max_tokens=1024) -> str:
        """Phase 7: lazy `import anthropic` + messages.create(...)."""
        raise NotImplementedError("Phase 7")


class GeminiClient(LLMClient):
    def __init__(self, api_key: str, model: str):
        self.api_key = api_key
        self.model = model

    def complete(self, messages, temperature=0.7, max_tokens=1024) -> str:
        """Phase 7: lazy `import google.generativeai` + generate_content(...)."""
        raise NotImplementedError("Phase 7")


_CLASSES = {
    "openai": OpenAIClient,
    "anthropic": AnthropicClient,
    "gemini": GeminiClient,
}


def get_client(provider: str | None = None, api_key: str | None = None, model: str | None = None) -> LLMClient:
    """Factory reading env defaults (LLM_PROVIDER / LLM_API_KEY / LLM_MODEL)."""
    provider = (provider or os.getenv("LLM_PROVIDER", "openai")).lower()
    if provider not in PROVIDERS:
        raise ValueError(f"Unknown LLM provider: {provider!r}. Expected one of {PROVIDERS}")
    api_key = api_key or os.getenv("LLM_API_KEY", "")
    model = model or os.getenv("LLM_MODEL", "")
    return _CLASSES[provider](api_key=api_key, model=model)
