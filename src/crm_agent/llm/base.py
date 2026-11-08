"""Provider-agnostic LLM interface.

The agent depends only on ``LLMClient``; OpenAI, Anthropic or the offline ``NullLLM`` are
interchangeable. When no key is configured the system still works end-to-end using the
rule-based intent parser and template composer – so evaluators can run it with zero setup.
"""

from __future__ import annotations

import json
import re
from typing import Protocol


class LLMError(RuntimeError):
    pass


class LLMClient(Protocol):
    name: str

    @property
    def available(self) -> bool: ...

    def complete(self, system: str, user: str, json_mode: bool = False, max_tokens: int = 800) -> str: ...


class NullLLM:
    """Explicit 'no LLM' implementation – callers check ``available`` and use deterministic fallbacks."""

    name = "offline-rules"

    @property
    def available(self) -> bool:
        return False

    def complete(self, system: str, user: str, json_mode: bool = False, max_tokens: int = 800) -> str:
        raise LLMError("No LLM configured")


def parse_json_response(text: str) -> dict:
    """Robustly extract a JSON object from an LLM reply (handles ```json fences / chatter)."""
    text = text.strip()
    fence = re.search(r"```(?:json)?\s*(\{.*\})\s*```", text, re.S)
    if fence:
        text = fence.group(1)
    else:
        start, end = text.find("{"), text.rfind("}")
        if start != -1 and end != -1:
            text = text[start:end + 1]
    try:
        return json.loads(text)
    except json.JSONDecodeError as exc:
        raise LLMError(f"LLM did not return valid JSON: {exc}") from exc
