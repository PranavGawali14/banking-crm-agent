"""Concrete LLM providers + factory. SDKs are imported lazily so they stay optional."""

from __future__ import annotations

import os

from crm_agent.config import Settings, get_settings
from crm_agent.llm.base import LLMClient, LLMError, NullLLM


class OpenAIClient:
    def __init__(self, model: str, temperature: float = 0.4, timeout: float = 30.0):
        self.name = f"openai:{model}"
        self.model, self.temperature, self.timeout = model, temperature, timeout
        self._client = None

    @property
    def available(self) -> bool:
        return bool(os.getenv("OPENAI_API_KEY"))

    def _get(self):
        if self._client is None:
            try:
                from openai import OpenAI
            except ImportError as exc:  # pragma: no cover
                raise LLMError("pip install openai") from exc
            self._client = OpenAI(timeout=self.timeout)
        return self._client

    def complete(self, system: str, user: str, json_mode: bool = False, max_tokens: int = 800) -> str:
        try:
            kwargs = {"response_format": {"type": "json_object"}} if json_mode else {}
            resp = self._get().chat.completions.create(
                model=self.model, temperature=self.temperature, max_tokens=max_tokens,
                messages=[{"role": "system", "content": system}, {"role": "user", "content": user}], **kwargs)
            return resp.choices[0].message.content or ""
        except LLMError:
            raise
        except Exception as exc:  # network, auth, rate limit …
            raise LLMError(f"OpenAI call failed: {exc}") from exc


class AnthropicClient:
    def __init__(self, model: str, temperature: float = 0.4, timeout: float = 30.0):
        self.name = f"anthropic:{model}"
        self.model, self.temperature, self.timeout = model, temperature, timeout
        self._client = None

    @property
    def available(self) -> bool:
        return bool(os.getenv("ANTHROPIC_API_KEY"))

    def _get(self):
        if self._client is None:
            try:
                import anthropic
            except ImportError as exc:  # pragma: no cover
                raise LLMError("pip install anthropic") from exc
            self._client = anthropic.Anthropic(timeout=self.timeout)
        return self._client

    def complete(self, system: str, user: str, json_mode: bool = False, max_tokens: int = 800) -> str:
        try:
            if json_mode:
                user += "\n\nRespond with a single valid JSON object only."
            resp = self._get().messages.create(
                model=self.model, max_tokens=max_tokens, temperature=self.temperature, system=system,
                messages=[{"role": "user", "content": user}])
            return "".join(b.text for b in resp.content if getattr(b, "type", "") == "text")
        except LLMError:
            raise
        except Exception as exc:
            raise LLMError(f"Anthropic call failed: {exc}") from exc


def build_llm(settings: Settings | None = None) -> LLMClient:
    s = settings or get_settings()
    provider = s.llm_provider
    openai = OpenAIClient(s.openai_model, s.llm_temperature, s.llm_timeout_s)
    anthropic = AnthropicClient(s.anthropic_model, s.llm_temperature, s.llm_timeout_s)
    if provider == "openai":
        return openai if openai.available else NullLLM()
    if provider == "anthropic":
        return anthropic if anthropic.available else NullLLM()
    if provider in ("none", "offline", "rules"):
        return NullLLM()
    # auto
    for client in (anthropic, openai):
        if client.available:
            return client
    return NullLLM()
