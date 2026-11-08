"""Responder: turns the blackboard of tool outputs into an RM-facing answer.

Everything in the answer is derived from tool outputs (numbers, reasons, offers), so each
claim is traceable to a step in the reasoning trace – no free-floating LLM narrative.
"""

from __future__ import annotations

from crm_agent.models import AgentResponse, IntentType, OutreachMessage, Plan
from crm_agent.outreach.templates import format_inr

def suggest_follow_ups(intent, prospects: list[dict], msgs: list) -> list[str]:
    """Context-aware next questions, so the RM discovers the conversational capabilities."""
    out = []
    if not intent.filters.cities and prospects:
        out.append(f"Only show customers in {prospects[0]['city']}")
    elif not intent.top_k or intent.top_k > 3:
        out.append("Top 3 only")
    if prospects:
        first = prospects[0]["first_name"]
        dup = sum(1 for p in prospects if p["first_name"] == first) > 1
        out.append(f"Why was {prospects[0]['full_name'] if dup else first} selected?")
    if msgs:
        lang = intent.language if intent.language not in (None, "preferred") else None
        out.append("Rewrite the messages in English" if lang == "Hindi" else "Rewrite the messages in Hindi")
        if intent.channel != "email":
            out.append("Send them as email instead")
    else:
        out.append("Generate WhatsApp messages for them")
    out.append("Export this campaign")
    return out[:4]


def _offer_txt(p: dict) -> str:
    o = p.get("offer") or {}
    if not o:
        return "–"
    if o["type"] == "loan":
        return f"₹{format_inr(o['amount'])} @ {o['rate']}%"
    if o["type"] == "card":
        return f"limit ₹{format_inr(o['amount'])}"
    if o["type"] == "deposit":
        return f"{o['rate']}% p.a."
    return f"SIP ₹{format_inr(o['amount'])}/mo"


def prospects_table(prospects: list[dict]) -> str:
    lines = ["| # | Customer | City | Value | Propensity | Why now | Offer | Next best |",
             "|---|---|---|---|---|---|---|---|"]
    for i, p in enumerate(prospects, 1):
        lines.append(f"| {i} | {p['full_name']} ({p['customer_id']}) | {p['city']} | {p.get('value_tier', '')} "
                     f"({p.get('value_score', 0):.0f}) | {p.get('propensity_pct', '–')}% | {', '.join(p.get('drivers', [])[:2]) or '–'} "
                     f"| {_offer_txt(p)} | {p.get('next_best_product_name') or '–'} |")
    return "\n".join(lines)


def message_block(m: OutreachMessage) -> str:
    status = "✅ compliant" if m.compliance_passed else "⚠️ check"
    status += "" if m.deliverable else " · 🚫 not deliverable"
    head = f"**{m.customer_name}** ({m.customer_id}) · {m.channel} · {m.language} · {status} · _{m.generated_by}_"
    subj = f"Subject: {m.subject}\n\n" if m.subject else ""
    notes = f"\n_notes: {'; '.join(m.compliance_notes)}_" if m.compliance_notes else ""
    return f"{head}\n```text\n{subj}{m.body}\n```{notes}"


def to_markdown(resp: AgentResponse) -> str:
    parts = [resp.text]
    if resp.messages:
        parts.append("#### ✉️ Outreach messages\n\n" + "\n\n".join(message_block(m) for m in resp.messages))
    return "\n\n".join(parts)


class Responder:
    def __init__(self, products: dict, lookback_days: int = 90):
        self.products = products
        self.lookback_days = lookback_days

    def respond(self, plan: Plan, bb: dict, trace, notes: list[str], state) -> AgentResponse:
        it = plan.intent.type
        failed = next((e for e in trace if e.status == "error"), None)
        if failed:
            text = f"I couldn't complete **{plan.goal}** – step `{failed.tool}` failed: {failed.summary}."
            if failed.tool == "get_customer_profile":
                text += " Try a customer id like `C0042` or a full name."
            if failed.tool == "export_campaign":
                text += " Ask me to find prospects first."
            return AgentResponse(text=text, intent=plan.intent, plan=plan, trace=trace)
        handler = {
            IntentType.FIND_PROSPECTS: self._find, IntentType.REFINE: self._find,
            IntentType.GENERATE_MESSAGES: self._messages, IntentType.EXPLAIN_CUSTOMER: self._explain,
            IntentType.CUSTOMER_PROFILE: self._profile, IntentType.LIST_PRODUCTS: self._products,
            IntentType.EXPORT: self._export,
        }.get(it, self._help)
        resp = handler(plan, bb, notes, state)
        resp.intent, resp.plan, resp.trace = plan.intent, plan, trace
        return resp

    # -- handlers -------------------------------------------------------------------------
    def _find(self, plan, bb, notes, state) -> AgentResponse:
        intent = plan.intent
        pname = self.products[intent.product_id]["name"]
        prospects = bb.get("prospects", [])
        elig = bb.get("eligibility", {})
        prop = bb.get("propensity", {})
        lines = [f"### 🎯 {plan.goal}"]
        if intent.is_follow_up:
            lines.append(f"_Refined previous search · filters: {intent.filters.describe()}_")
        lines.append(f"**Funnel:** {len(bb.get('customers', []))} customers scanned → {len(bb.get('high_value', []))} high-value → "
                     f"{len(elig.get('eligible', []))} eligible for {pname} → **{len(prospects)} shortlisted**")
        if elig.get("rejection_counts"):
            top = sorted(elig["rejection_counts"].items(), key=lambda kv: kv[1], reverse=True)[:4]
            lines.append("**Excluded by policy:** " + ", ".join(f"{k} ({v})" for k, v in top))
        metrics = prop.get("model_metrics") or {}
        if prop.get("model"):
            lines.append(f"**Propensity model:** `{prop['model']}`" + (f" · held-out AUC {metrics['test_auc']} on {metrics['train_rows'] + metrics['test_rows']:,} past campaign outcomes" if metrics.get("test_auc") else " · transparent signal weights (no campaign history yet)"))
        lines += [f"> ℹ️ {n}" for n in notes]
        if not prospects:
            lines.append("\nNo customer met every criterion. Try widening filters (e.g. remove the city) or another product.")
            return AgentResponse(text="\n\n".join(lines))
        lines.append(prospects_table(prospects))
        msgs = bb.get("messages", [])
        if msgs:
            ok = sum(1 for m in msgs if m.compliance_passed and m.deliverable)
            rerouted = sum(1 for m in msgs if any("re-routed" in n for n in m.compliance_notes))
            lines.append(f"**Outreach:** {len(msgs)} drafts · {ok} compliant & deliverable" + (f" · {rerouted} re-routed to a consented channel" if rerouted else ""))
        artifacts = [bb["export"]["csv"]] if bb.get("export") else []
        if artifacts:
            lines.append(f"📁 Campaign file: `{artifacts[0]}`")
        lines.append("_Try next:_ " + " · ".join(f"“{s}”" for s in suggest_follow_ups(intent, prospects, msgs)))
        return AgentResponse(text="\n\n".join(lines), prospects=prospects, messages=msgs, artifacts=artifacts)

    def _messages(self, plan, bb, notes, state) -> AgentResponse:
        msgs = bb.get("messages", [])
        ok = sum(1 for m in msgs if m.compliance_passed and m.deliverable)
        text = (f"### ✉️ {plan.goal}\n\n{ok}/{len(msgs)} messages are compliant and deliverable."
                + (f"\n\n📁 Campaign file: `{bb['export']['csv']}`" if bb.get("export") else ""))
        return AgentResponse(text=text, prospects=state.prospects, messages=msgs,
                             artifacts=[bb["export"]["csv"]] if bb.get("export") else [])

    def _explain(self, plan, bb, notes, state) -> AgentResponse:
        cands = bb.get("customers", [])
        if len(cands) > 1:
            names = ", ".join(f"{c['full_name']} ({c['customer_id']})" for c in cands[:6])
            return AgentResponse(text=f"I found several customers matching **{plan.intent.customer_ref}**: {names}. Which one do you mean?")
        p = bb["propensity"]["ranked"][0]
        v = next(x for x in bb["valued"] if x["customer_id"] == p["customer_id"])
        elig = bb["eligibility"]
        rejected = next((r for r in elig["rejected"] if r["customer_id"] == p["customer_id"]), None)
        pname = self.products[plan.intent.product_id]["name"]
        rank = next((i for i, x in enumerate(state.prospects, 1) if x["customer_id"] == p["customer_id"]), None)
        s = p["feature_summary"]
        contrib = sorted(p["contributions"].items(), key=lambda kv: abs(kv[1]), reverse=True)[:6]
        lines = [f"### 🔍 Why {p['full_name']} ({p['customer_id']}) for {pname}?",
                 f"**Value:** {v['value_tier']} ({v['value_score']:.0f}/100) – components: " +
                 ", ".join(f"{k} {val:.2f}" for k, val in v["value_components"].items()),
                 f"**Conversion propensity this month:** {p['propensity_pct']}% (`{p['model']}`)" +
                 (f" → ranked **#{rank}** in the current shortlist" if rank else " → not in the current shortlist"),
                 "**Positive drivers:** " + (", ".join(p["drivers"]) or "none significant"),
                 "**Holding back:** " + (", ".join(p["risk_factors"]) or "nothing material"),
                 "**Policy check:** " + ("✅ eligible" if not rejected else "❌ " + "; ".join(rejected["reasons"])),
                 f"**Last {self.lookback_days} days (RM-internal, never shown to customer):** monthly spend ≈ ₹{format_inr(s['monthly_spend_avg'])}, "
                 f"spend change {s['spend_growth_pct']:+d}%, big-ticket spends ₹{format_inr(s['big_ticket_spend_45d'])}"
                 + (f" ({s['detected_life_event'].replace('_', ' ')})" if s["detected_life_event"] else "")
                 + f", balance dip {s['balance_dip_pct']}%, EMI/income {s['dti_pct']}%",
                 "| Feature | Contribution |\n|---|---|\n" + "\n".join(f"| {k} | {val:+.2f} |" for k, val in contrib)]
        return AgentResponse(text="\n\n".join(lines), prospects=[p])

    def _profile(self, plan, bb, notes, state) -> AgentResponse:
        cands = bb.get("prospects", [])
        if len(cands) > 1:
            names = ", ".join(f"{c['full_name']} ({c['customer_id']})" for c in cands[:6])
            return AgentResponse(text=f"Several customers match **{plan.intent.customer_ref}**: {names}. Which one?")
        c = cands[0]
        s = bb["features"][c["customer_id"]]["summary"]
        consent = ", ".join(ch for ch, flag in (("WhatsApp", c["whatsapp_opt_in"]), ("SMS", c["sms_opt_in"] and not c["dnd"]),
                                                  ("Email", c["email_opt_in"])) if flag) or "none"
        lines = [f"### 👤 {c['full_name']} ({c['customer_id']})",
                 f"{c['age']} · {c['occupation']} ({c['employment_type'].replace('_', '-')}) · {c['city']} · prefers {c['preferred_language']}",
                 f"**Segment:** {c['segment']} · **Value:** {c['value_tier']} ({c['value_score']:.0f}) · **Tenure:** {c['relationship_years']} yrs · "
                 f"**Credit score:** {c['credit_score']} · **Income:** ₹{format_inr(c['annual_income'])}/yr",
                 f"**Holds:** {', '.join(p.replace('_', ' ') for p in c['existing_products'])}",
                 f"**Consented channels:** {consent}" + (" · ⚠️ DND" if c["dnd"] else ""),
                 f"**Recent behaviour:** spend ≈ ₹{format_inr(s['monthly_spend_avg'])}/mo ({s['spend_growth_pct']:+d}% last 30d), "
                 f"top categories {', '.join(s['top_spend_categories'])}" +
                 (f", life-event signal: **{s['detected_life_event'].replace('_', ' ')}**" if s["detected_life_event"] else ""),
                 f"**Best-fit product:** {c.get('recommended_product_name') or '–'} ({_offer_txt(c)})"
                 + (f" · next: {c['next_best_product_name']}" if c.get("next_best_product_name") else "")]
        return AgentResponse(text="\n\n".join(lines), prospects=[c])

    def _products(self, plan, bb, notes, state) -> AgentResponse:
        rows = bb["products"]
        table = "| Product | Category | Min income | Min score | Age | Model |\n|---|---|---|---|---|---|\n" + "\n".join(
            f"| {r['name']} (`{r['product_id']}`) | {r['category']} | ₹{format_inr(r['min_income'])} | {r['min_credit_score']} | {r['age']} | `{r['model']}` |"
            for r in rows)
        return AgentResponse(text="### 🏦 Product catalogue\n\n" + table)

    def _export(self, plan, bb, notes, state) -> AgentResponse:
        e = bb["export"]
        return AgentResponse(text=f"📁 Exported the current campaign:\n\n- `{e['csv']}`\n- `{e['json']}`", artifacts=[e["csv"], e["json"]])

    def _help(self, plan, bb, notes, state) -> AgentResponse:
        return AgentResponse(text=HELP_TEXT)


HELP_TEXT = """### 🤖 I'm your CRM co-pilot. Try:
- **Find high-value customers likely to convert for a personal loan this month and generate personalized WhatsApp messages**
- *Only show the ones in Pune* · *Top 3 only* · *Income above 20 lakh*
- *Rewrite the messages in Hindi* · *Send them as email instead*
- *Why was Priya selected?* · *Tell me about C0042*
- *Which customers should get a credit card upgrade?* · *Find FD prospects among retirees*
- *What products do we have?* · *Export this campaign*

Commands: `/trace` show last reasoning trace · `/state` show memory · `/reset` new conversation · `/quit`"""
