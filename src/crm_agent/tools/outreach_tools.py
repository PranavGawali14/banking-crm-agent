"""Engagement tools: personalised message generation, compliance validation, campaign export."""

from __future__ import annotations

import csv
import json
from datetime import datetime
from typing import Any, Optional

from crm_agent.models import Channel, OutreachMessage, ToolResult
from crm_agent.tools.base import Tool, ToolArgs, ToolContext


class GenerateOutreachMessages(Tool):
    name = "generate_outreach_messages"
    description = ("Write a personalised outreach message per customer for the chosen channel and language using a sanitised "
                   "customer brief (LLM when configured, multilingual templates otherwise).")

    class Args(ToolArgs):
        prospects: list[dict[str, Any]]
        product_id: str
        channel: Channel = "whatsapp"
        language: Optional[str] = None  # None => each customer's preferred language

    def run(self, ctx: ToolContext, args: Args) -> ToolResult:
        cfg = ctx.products[args.product_id]
        msgs = [ctx.composer.compose(p, args.product_id, cfg, args.channel, args.language) for p in args.prospects if p.get("offer")]
        by = {m.generated_by for m in msgs}
        langs = sorted({m.language for m in msgs})
        return ToolResult(data=msgs, summary=f"Drafted {len(msgs)} {args.channel} messages ({', '.join(langs) or '-'}) via {', '.join(sorted(by)) or '-'}")


class CheckMessageCompliance(Tool):
    name = "check_message_compliance"
    description = ("Validate every message (consent/DND, banned claims, disclaimers, opt-out, length, PII leakage); auto-repair, "
                   "regenerate unsafe drafts with the safe template, and re-route to a consented channel when needed.")

    class Args(ToolArgs):
        messages: list[Any]
        prospects: list[dict[str, Any]]
        product_id: str
        auto_reroute: bool = True

    def run(self, ctx: ToolContext, args: Args) -> ToolResult:
        cfg = ctx.products[args.product_id]
        by_id = {p["customer_id"]: p for p in args.prospects}
        out: list[OutreachMessage] = []
        regenerated = rerouted = blocked = 0
        for raw in args.messages:
            msg = raw if isinstance(raw, OutreachMessage) else OutreachMessage(**raw)
            p = by_id[msg.customer_id]
            checked, hard_fail = ctx.checker.check(msg, p, cfg["category"])
            if hard_fail:  # repair loop: fall back to the deterministic, pre-approved template
                regenerated += 1
                safe = ctx.composer.compose_template(p, args.product_id, cfg, msg.channel,
                                                      msg.language if msg.language in ("English", "Hindi", "Marathi") else "English")
                checked, _ = ctx.checker.check(safe, p, cfg["category"])
                checked.compliance_notes = [*msg.compliance_notes, "LLM draft failed checks → regenerated from approved template", *checked.compliance_notes]
            if not checked.deliverable and args.auto_reroute and checked.fallback_channel:
                rerouted += 1
                alt = ctx.composer.compose(p, args.product_id, cfg, checked.fallback_channel, msg.language)
                alt_checked, alt_fail = ctx.checker.check(alt, p, cfg["category"])
                if alt_fail:
                    alt = ctx.composer.compose_template(p, args.product_id, cfg, checked.fallback_channel, "English")
                    alt_checked, _ = ctx.checker.check(alt, p, cfg["category"])
                alt_checked.compliance_notes.insert(0, f"re-routed from {msg.channel}: no consent on that channel")
                checked = alt_checked
            if not checked.deliverable:
                blocked += 1
            out.append(checked)
        ok = sum(1 for m in out if m.compliance_passed and m.deliverable)
        return ToolResult(data=out, summary=(f"{ok}/{len(out)} messages compliant & deliverable; {regenerated} regenerated, "
                                             f"{rerouted} re-routed to a consented channel, {blocked} blocked (no consent)"))


class ExportCampaign(Tool):
    name = "export_campaign"
    description = "Write the shortlisted prospects and approved messages to CSV/JSON for upload into the CRM / campaign tool."

    class Args(ToolArgs):
        prospects: list[dict[str, Any]]
        messages: list[Any] = []
        product_id: Optional[str] = None
        name: str = "campaign"

    def run(self, ctx: ToolContext, args: Args) -> ToolResult:
        if not args.prospects:
            return ToolResult(ok=False, error="nothing to export – run a prospect search first", summary="nothing to export")
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        base = ctx.settings.output_dir / f"{args.name}_{args.product_id or 'mixed'}_{ts}"
        msgs = {(m.customer_id if isinstance(m, OutreachMessage) else m["customer_id"]):
                (m if isinstance(m, OutreachMessage) else OutreachMessage(**m)) for m in args.messages}
        rows = []
        for rank, p in enumerate(args.prospects, 1):
            m = msgs.get(p["customer_id"])
            offer = p.get("offer") or {}
            rows.append({
                "rank": rank, "customer_id": p["customer_id"], "name": p["full_name"], "city": p["city"],
                "segment": p.get("segment"), "value_tier": p.get("value_tier"), "value_score": p.get("value_score"),
                "propensity_pct": p.get("propensity_pct"), "drivers": "; ".join(p.get("drivers", [])),
                "product": p.get("recommended_product_name"), "offer_amount": offer.get("amount"), "offer_rate": offer.get("rate"),
                "next_best_product": p.get("next_best_product_name"),
                "channel": m.channel if m else None, "language": m.language if m else None,
                "deliverable": m.deliverable if m else None, "compliance_passed": m.compliance_passed if m else None,
                "message_subject": m.subject if m else None, "message": m.body if m else None,
            })
        csv_path, json_path = base.with_suffix(".csv"), base.with_suffix(".json")
        with csv_path.open("w", newline="", encoding="utf-8") as fh:
            w = csv.DictWriter(fh, fieldnames=list(rows[0]))
            w.writeheader()
            w.writerows(rows)
        json_path.write_text(json.dumps(rows, indent=2, ensure_ascii=False, default=str), encoding="utf-8")
        return ToolResult(data={"csv": _display(csv_path), "json": _display(json_path)}, summary=f"Exported {len(rows)} records → {csv_path.name}")


def _display(path) -> str:
    """Project-relative path when possible (keeps transcripts free of machine-specific paths)."""
    from crm_agent.config import PROJECT_ROOT

    try:
        return str(path.resolve().relative_to(PROJECT_ROOT))
    except ValueError:
        return str(path)
