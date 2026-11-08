"""Compliance guardrail – the 'critic' in the generate → validate → repair loop.

Checks every outreach message against config/compliance_rules.json:
consent per channel, DND, banned/misleading phrases, mandatory disclaimer & opt-out text,
channel length limits and PII / transaction leakage. Fixable issues are auto-repaired;
unfixable ones are reported so the caller can regenerate with the safe template.
"""

from __future__ import annotations

import re

from crm_agent.models import OutreachMessage


class ComplianceChecker:
    def __init__(self, rules: dict):
        self.rules = rules

    def consent_ok(self, prospect: dict, channel: str) -> bool:
        ch = self.rules["channels"][channel]
        if ch.get("blocked_by_dnd") and prospect.get("dnd"):
            return False
        return bool(prospect.get(ch["requires_opt_in"], False))

    def fallback_channel(self, prospect: dict, exclude: str) -> str | None:
        for ch in ("whatsapp", "email", "sms"):
            if ch != exclude and self.consent_ok(prospect, ch):
                return ch
        return None

    def check(self, msg: OutreachMessage, prospect: dict, category: str) -> tuple[OutreachMessage, bool]:
        """Return (possibly repaired message, needs_regeneration)."""
        notes: list[str] = []
        body = msg.body
        hard_fail = False
        ch_rules = self.rules["channels"][msg.channel]

        lowered = body.lower()
        for phrase in self.rules["banned_phrases"]:
            if phrase in lowered:
                notes.append(f"banned phrase '{phrase}'")
                hard_fail = True
        for name, pattern in self.rules["pii_patterns"].items():
            if re.search(pattern, body):
                notes.append(f"possible PII/transaction leakage ({name})")
                hard_fail = True

        disclaimer = self.rules["required_disclaimers"].get(category, "T&C apply.")
        if disclaimer.lower().rstrip(".") not in lowered:
            body = f"{body.rstrip()}\n{disclaimer}"
            notes.append("auto-added mandatory disclaimer")
        opt_out = self.rules["opt_out_text"][msg.channel]
        if ch_rules.get("requires_opt_out_text") and opt_out.lower().rstrip(".") not in body.lower():
            body = f"{body.rstrip()} {opt_out}"
            notes.append("auto-added opt-out text")
        if len(body) > ch_rules["max_chars"]:
            notes.append(f"too long for {msg.channel} ({len(body)}>{ch_rules['max_chars']} chars)")
            hard_fail = True

        deliverable = self.consent_ok(prospect, msg.channel)
        fallback = None
        if not deliverable:
            fallback = self.fallback_channel(prospect, msg.channel)
            reason = "on DND" if (prospect.get("dnd") and ch_rules.get("blocked_by_dnd")) else f"no {msg.channel} opt-in"
            notes.append(f"not deliverable: {reason}" + (f" → use {fallback}" if fallback else " → no consented channel"))

        repaired = msg.model_copy(update={
            "body": body, "compliance_passed": not hard_fail, "deliverable": deliverable,
            "fallback_channel": fallback, "compliance_notes": [*msg.compliance_notes, *notes],
        })
        return repaired, hard_fail
