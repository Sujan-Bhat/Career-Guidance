"""Provider-agnostic LLM client (Part A).

One interface, three adapters (OpenAI / Anthropic / Gemini). SDK imports are
lazy so the package installs without any provider SDK; keys are read from the
environment (LLM_PROVIDER, LLM_API_KEY, LLM_MODEL) with per-call overrides.
Gemini additionally walks LLM_FALLBACK_MODELS when the primary model hits its
per-model daily quota (429) or is unavailable (404).
"""
import logging
import os
from abc import ABC, abstractmethod

logger = logging.getLogger(__name__)

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
        if not self.api_key:
            raise RuntimeError("LLM_API_KEY is not configured")
        from openai import OpenAI  # lazy: optional provider SDK

        client = OpenAI(api_key=self.api_key)
        response = client.chat.completions.create(
            model=self.model or "gpt-4o-mini",
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
        )
        return (response.choices[0].message.content or "").strip()


class AnthropicClient(LLMClient):
    def __init__(self, api_key: str, model: str):
        self.api_key = api_key
        self.model = model

    def complete(self, messages, temperature=0.7, max_tokens=1024) -> str:
        if not self.api_key:
            raise RuntimeError("LLM_API_KEY is not configured")
        from anthropic import Anthropic  # lazy: optional provider SDK

        client = Anthropic(api_key=self.api_key)
        system = "\n\n".join(m["content"] for m in messages if m["role"] == "system")
        kwargs = {
            "model": self.model or "claude-3-5-sonnet-latest",
            "messages": [m for m in messages if m["role"] != "system"],
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        if system:
            kwargs["system"] = system
        response = client.messages.create(**kwargs)
        return "".join(
            block.text for block in response.content if getattr(block, "type", None) == "text"
        ).strip()


def _model_chain(model: str | None) -> list[str]:
    """[primary] + LLM_FALLBACK_MODELS (comma-separated), deduplicated, order
    preserved. Unset fallbacks yield a one-model chain — identical behaviour
    to before failover existed."""
    primary = (model or "").strip() or "gemini-1.5-flash"  # the legacy default
    fallbacks = [
        m.strip() for m in os.getenv("LLM_FALLBACK_MODELS", "").split(",") if m.strip()
    ]
    chain = [primary]
    for candidate in fallbacks:
        if candidate not in chain:
            chain.append(candidate)
    return chain


def _is_failover_error(exc: BaseException) -> bool:
    """Quota (429) and retired/unavailable-model (404) errors are properties
    of the configured model — each model has its own free-tier daily bucket,
    and Google retires models outright. Both justify trying the next
    candidate. Everything else (bad API key, malformed request, safety
    block) must surface immediately so bugs stay visible."""
    try:
        from google.api_core import exceptions as api_errors
    except Exception:  # noqa: BLE001 — SDK layout changed: nothing to classify
        return False
    if isinstance(exc, (api_errors.ResourceExhausted, api_errors.NotFound)):
        return True
    lowered = str(exc).lower()
    return (
        "resource_exhausted" in lowered
        or "quota" in lowered
        or ("404" in lowered and "not found" in lowered)
    )


class GeminiClient(LLMClient):
    """Gemini adapter with automatic model failover (free-tier resilience)."""

    def __init__(self, api_key: str, model: str):
        self.api_key = api_key
        self.models = _model_chain(model)
        self.model = self.models[0]

    def complete(self, messages, temperature=0.7, max_tokens=1024) -> str:
        if not self.api_key:
            raise RuntimeError("LLM_API_KEY is not configured")
        import google.generativeai as genai  # lazy: optional provider SDK

        genai.configure(api_key=self.api_key)
        system = "\n\n".join(m["content"] for m in messages if m["role"] == "system")
        # flatten the chat history into one grounded prompt
        parts = [
            f"{'Student' if m['role'] == 'user' else 'Assistant'}: {m['content']}"
            for m in messages
            if m["role"] != "system"
        ]
        # Thinking-era Gemini models spend the output budget on invisible
        # reasoning before emitting any text, so a caller-sized cap truncates
        # the visible answer mid-JSON. Pad the cap with headroom so the
        # requested budget applies to the VISIBLE response.
        generation_config = {
            "temperature": temperature,
            "max_output_tokens": max_tokens + GEMINI_THINKING_HEADROOM,
        }

        last_error: Exception | None = None
        for model_name in self.models:
            model = genai.GenerativeModel(model_name, system_instruction=system or None)
            try:
                response = model.generate_content(parts, generation_config=generation_config)
            except Exception as exc:  # noqa: BLE001 — classified in _is_failover_error
                if not _is_failover_error(exc):
                    raise
                last_error = exc
                logger.warning(
                    "Gemini model %s unavailable (%s: %.120s) — failing over",
                    model_name,
                    type(exc).__name__,
                    exc,
                )
                continue
            return (response.text or "").strip()

        assert last_error is not None  # the chain is never empty
        raise last_error


# Invisible reasoning tokens consumed before the visible answer; observed
# ~1400 on quiz generation with max_tokens=1500 (only 57 visible tokens).
GEMINI_THINKING_HEADROOM = 2048

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
