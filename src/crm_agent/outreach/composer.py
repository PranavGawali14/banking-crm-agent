"""Outreach composer: LLM-first, template fallback.

The composer only ever sees a *sanitised brief* (first name, tier, tenure, offer, a generic
"need hint") – never raw transactions – which is how we personalise without being creepy or
leaking data into prompts.
"""

from __future__ import annotations

import json

from crm_agent.config import Settings
from crm_agent.llm.base import LLMClient, LLMError, parse_json_response
from crm_agent.llm.prompts import CHANNEL_RULES, MESSAGE_SYSTEM, MESSAGE_USER
from crm_agent.models import OutreachMessage
from crm_agent.outreach.templates import HOOKS, SMS_TEXT, SUPPORTED_LANGUAGES, TEXT, format_inr

NEED_HINTS = {  # generic hint passed to the LLM instead of raw data
    "wedding": "may have family celebrations coming up",
    "travel": "may be planning a big trip",
    "education": "may be planning education expenses",
    "medical": "may have had unexpected expenses recently",
    "home_improvement": "may be upgrading their home",
    "electronics": "may be planning a big purchase",
    "balance_dip": "may value keeping their savings cushion intact",
    "digital": "has shown interest in loan options on our app",
    "dining": "enjoys dining out",
    "travel_card": "travels regularly",
    "shopping": "shops online frequently",
    "rent": "currently pays rent",
    "idle": "keeps a healthy savings balance",
    "default": "valued long-standing customer",
}


def pick_hook(prospect: dict, product_id: str) -> str:
    """Choose the single most relevant 'need hook' from the customer's behavioural signals."""
    summary = prospect.get("feature_summary", {})
    signals = prospect.get("signals", {})
    if product_id in ("personal_loan", "auto_loan"):
        if summary.get("detected_life_event"):
            return summary["detected_life_event"]
        if signals.get("loan_page_visits", 0) >= 0.3:
            return "digital"
        if signals.get("balance_dip", 0) >= 0.25:
            return "balance_dip"
    if product_id == "credit_card_premium":
        options = {"travel_card": signals.get("travel_spend", 0), "dining": signals.get("dining_spend", 0),
                   "shopping": signals.get("shopping_spend", 0)}
        best = max(options, key=options.get)
        return best if options[best] > 0.1 else "default"
    if product_id == "home_loan" and signals.get("rent_paid", 0) > 0.2:
        return "rent"
    if product_id in ("fixed_deposit", "mutual_fund_sip"):
        return "idle"
    return "default"


def resolve_language(requested: str | None, prospect: dict) -> str:
    return (requested or prospect.get("preferred_language") or "English").strip().title()


class OutreachComposer:
    def __init__(self, llm: LLMClient, settings: Settings, compliance_rules: dict):
        self.llm = llm
        self.settings = settings
        self.rules = compliance_rules

    # -- public ----------------------------------------------------------------------
    def compose(self, prospect: dict, product_id: str, product_cfg: dict, channel: str, language: str | None) -> OutreachMessage:
        lang = resolve_language(language, prospect)
        if self.llm.available:
            try:
                return self._compose_llm(prospect, product_id, product_cfg, channel, lang)
            except LLMError:
                pass  # graceful degradation -> deterministic template
        template_lang = lang if lang in SUPPORTED_LANGUAGES else "English"
        msg = self.compose_template(prospect, product_id, product_cfg, channel, template_lang)
        if template_lang != lang:
            msg.compliance_notes.append(f"{lang} template unavailable offline – used English (configure an LLM for {lang}).")
        return msg

    # -- brief -----------------------------------------------------------------------
    def _vars(self, p: dict, product_id: str, product_cfg: dict) -> dict:
        offer = p.get("offer") or {}
        years = int(p.get("relationship_years", 0))
        return {
            "first_name": p["first_name"], "last_name": p["last_name"],
            "salutation": "Mr." if p.get("gender") == "M" else "Ms.",
            "bank": self.settings.bank_name, "rm_name": self.settings.rm_name, "rm_phone": self.settings.rm_phone,
            "years": years, "tier": p.get("value_tier", "valued"),
            "headline": product_cfg["offer"].get("headline", product_cfg["name"]),
            "amount": format_inr(offer.get("amount", 0)), "rate": offer.get("rate", ""),
            "emi": format_inr(offer.get("emi", 0)), "tenure": offer.get("tenure_months", 36),
            "bonus": product_cfg["offer"].get("senior_bonus", 0),
            "hook": pick_hook(p, product_id),
            "category": product_cfg["category"], "product_name": product_cfg["name"],
        }

    def _disclaimer(self, category: str) -> str:
        return self.rules["required_disclaimers"].get(category, "T&C apply.")

    # -- template path ---------------------------------------------------------------------
    def _offer_line(self, t: dict, v: dict, offer_type: str, is_senior: bool) -> str:
        key = {"loan": "loan", "card": "card", "deposit": "deposit", "investment": "investment"}[offer_type]
        senior = t["senior"].format(**v) if (offer_type == "deposit" and is_senior and v["bonus"]) else ""
        line = t[key].format(**{**v, "senior": senior})
        if offer_type == "loan" and v["product_name"] != "Personal Loan" and t is not TEXT["English"]:
            # non-English loan line is written for personal loans; swap in the actual product name
            line = line.replace("पर्सनल लोन", v["product_name"])
        return line

    def compose_template(self, p: dict, product_id: str, cfg: dict, channel: str, lang: str) -> OutreachMessage:
        t, v = TEXT[lang], self._vars(p, product_id, cfg)
        offer_type = cfg["offer"]["type"]
        hook = HOOKS[lang].get(v["hook"], HOOKS[lang]["default"])
        disclaimer = self._disclaimer(cfg["category"])
        opt_out = self.rules["opt_out_text"][channel]
        formal = p.get("segment") in ("Wealth", "Priority")
        thanks = (t["thanks"] if v["years"] >= 1 else t["thanks_new"]).format(**v)
        offer_line = self._offer_line(t, v, offer_type, p.get("age", 0) >= 58)
        cta = t["cta_loan"] if offer_type == "loan" else t["cta"]

        if channel == "sms":
            amount = v["amount"]
            sms_offer = {
                "English": f"your {v['headline']} up to Rs {amount}{' @ ' + str(v['rate']) + '% p.a.' if offer_type == 'loan' else ''} is ready.",
                "Hindi": f"आपका {v['headline']} (Rs {amount} तक) तैयार है।",
                "Marathi": f"तुमचे {v['headline']} (Rs {amount} पर्यंत) तयार आहे.",
            }[lang]
            if offer_type in ("deposit", "investment"):
                rate = f" @ {v['rate']}% p.a." if offer_type == "deposit" else ""
                sms_offer = {"English": f"our {v['headline']}{rate} is now open for you.",
                             "Hindi": f"हमारा {v['headline']}{rate} आपके लिए उपलब्ध है।",
                             "Marathi": f"आमचे {v['headline']}{rate} तुमच्यासाठी उपलब्ध आहे."}[lang]
            body = SMS_TEXT[lang].format(**v, sms_offer=sms_offer) + f" {disclaimer} {opt_out}"
            return OutreachMessage(customer_id=p["customer_id"], customer_name=p["full_name"], channel="sms",
                                   language=lang, body=body, generated_by="template")

        if channel == "email":
            subject_key = "subject_loan" if offer_type == "loan" else "subject_other"
            subject = t[subject_key].format(**v)
            subject = subject[0].upper() + subject[1:]
            body = "\n\n".join([
                t["greet_email"].format(**v),
                f"{thanks} {offer_line}",
                f"{hook} {t['cta_email'].format(**v)}",
                t["sign_email"].format(**v),
                f"{disclaimer}\n{opt_out}",
            ])
            return OutreachMessage(customer_id=p["customer_id"], customer_name=p["full_name"], channel="email",
                                   language=lang, subject=subject, body=body, generated_by="template")

        greet = (t["greet_formal"] if formal else t["greet_casual"]).format(**v)
        body = "\n\n".join([greet, f"{thanks} {offer_line}", hook, cta, t["sign"].format(**v), f"*{disclaimer} {opt_out}"])
        return OutreachMessage(customer_id=p["customer_id"], customer_name=p["full_name"], channel="whatsapp",
                               language=lang, body=body, generated_by="template")

    # -- LLM path ------------------------------------------------------------------------------
    def _compose_llm(self, p: dict, product_id: str, cfg: dict, channel: str, lang: str) -> OutreachMessage:
        v = self._vars(p, product_id, cfg)
        brief = {
            "first_name": v["first_name"], "last_name": v["last_name"], "salutation": v["salutation"],
            "segment": p.get("segment"), "value_tier": v["tier"], "years_with_bank": v["years"],
            "occupation": p.get("occupation"), "city": p.get("city"),
            "product": cfg["name"], "offer_headline": v["headline"],
            "offer": {k: val for k, val in {
                "amount_inr": v["amount"], "indicative_rate_pct": v["rate"], "emi_inr": v["emi"],
                "tenure_months": v["tenure"] if cfg["offer"]["type"] == "loan" else None}.items() if val},
            "need_hint": NEED_HINTS.get(v["hook"], NEED_HINTS["default"]),
            "formality": "formal" if p.get("segment") in ("Wealth", "Priority") else "friendly",
        }
        system = MESSAGE_SYSTEM.format(bank=self.settings.bank_name, disclaimer=self._disclaimer(cfg["category"]),
                                       opt_out=self.rules["opt_out_text"][channel], language=lang, channel=channel,
                                       channel_rules=CHANNEL_RULES[channel])
        user = MESSAGE_USER.format(brief=json.dumps(brief, ensure_ascii=False, indent=2), channel=channel,
                                   rm_name=self.settings.rm_name, bank=self.settings.bank_name)
        data = parse_json_response(self.llm.complete(system, user, json_mode=True, max_tokens=700))
        body = (data.get("body") or "").strip()
        if not body:
            raise LLMError("empty body")
        return OutreachMessage(customer_id=p["customer_id"], customer_name=p["full_name"], channel=channel,
                               language=lang, subject=data.get("subject") if channel == "email" else None,
                               body=body, generated_by=self.llm.name)
