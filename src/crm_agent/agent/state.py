"""Conversation state / working memory.

Two layers:
* **Session memory** (``ConversationState``) – survives across turns: the last search intent,
  the current shortlist, its features, generated messages, chosen channel/language. This is what
  makes follow-ups like "only Pune", "now in Hindi" or "why Priya?" work.
* **Blackboard** (a plain dict per turn) – the scratch-pad the executor uses to pass tool outputs
  to later steps of the current plan.

State is JSON-serialisable and persisted per session id, so a CLI restart or a second UI tab
can resume the same conversation.
"""

from __future__ import annotations

import json
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

from pydantic import BaseModel, Field

from crm_agent.models import Intent, OutreachMessage, TraceEvent


class Turn(BaseModel):
    role: str
    content: str
    intent: Optional[str] = None
    at: str = Field(default_factory=lambda: datetime.now().isoformat(timespec="seconds"))


class ConversationState(BaseModel):
    session_id: str = Field(default_factory=lambda: uuid.uuid4().hex[:8])
    turns: list[Turn] = Field(default_factory=list)
    search_intent: Optional[Intent] = None   # last find/refine intent (for merging follow-ups)
    product_id: Optional[str] = None
    channel: Optional[str] = None
    language: Optional[str] = None
    prospects: list[dict[str, Any]] = Field(default_factory=list)
    features: dict[str, Any] = Field(default_factory=dict)
    messages: list[OutreachMessage] = Field(default_factory=list)
    funnel: dict[str, Any] = Field(default_factory=dict)
    last_trace: list[TraceEvent] = Field(default_factory=list)
    artifacts: list[str] = Field(default_factory=list)

    # -- helpers ----------------------------------------------------------------------
    def add_turn(self, role: str, content: str, intent: str | None = None) -> None:
        self.turns.append(Turn(role=role, content=content, intent=intent))
        self.turns = self.turns[-40:]  # bounded memory

    def has_cohort(self) -> bool:
        return bool(self.prospects)

    def find_prospect(self, ref: str) -> Optional[dict]:
        low = ref.lower().strip()
        for p in self.prospects:
            if low in (p["customer_id"].lower(), p["full_name"].lower(), p["first_name"].lower()):
                return p
        return None

    def context_summary(self) -> dict:
        """Compact context handed to the LLM intent parser (no PII beyond first names)."""
        return {
            "has_shortlist": self.has_cohort(),
            "shortlist_names": [p["first_name"] for p in self.prospects[:15]],
            "last_search": self.search_intent.model_dump(exclude={"raw_query", "parser"}) if self.search_intent else None,
            "channel": self.channel, "language": self.language, "product_id": self.product_id,
            "recent_turns": [t.content for t in self.turns[-4:] if t.role == "user"],
        }

    def reset(self) -> None:
        sid = self.session_id
        self.__dict__.update(ConversationState(session_id=sid).__dict__)

    # -- persistence -------------------------------------------------------------------
    def save(self, directory: Path) -> Path:
        directory.mkdir(parents=True, exist_ok=True)
        path = directory / f"{self.session_id}.json"
        path.write_text(self.model_dump_json(indent=1), encoding="utf-8")
        return path

    @classmethod
    def load(cls, directory: Path, session_id: str) -> "ConversationState":
        path = directory / f"{session_id}.json"
        if path.exists():
            return cls(**json.loads(path.read_text(encoding="utf-8")))
        return cls(session_id=session_id)
