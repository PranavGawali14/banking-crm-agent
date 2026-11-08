"""Intent understanding: natural language → structured ``Intent``.

* ``RuleBasedIntentParser`` – deterministic regex/keyword parser (offline, fast, testable).
* ``LLMIntentParser``       – asks the LLM for JSON matching the ``Intent`` schema, validates it
  with Pydantic and **falls back to the rule parser** on any error. The rule parser also
  post-validates LLM output (e.g. unknown product ids / cities are dropped).
"""

from __future__ import annotations

import json
import re
from typing import Optional

from pydantic import ValidationError

from crm_agent.agent.state import ConversationState
from crm_agent.llm.base import LLMClient, LLMError, parse_json_response
from crm_agent.llm.prompts import INTENT_SYSTEM
from crm_agent.models import CustomerFilters, Intent, IntentType

CITY_ALIASES = {"bangalore": "Bengaluru", "bombay": "Mumbai", "new delhi": "Delhi", "ncr": "Delhi",
                "madras": "Chennai", "calcutta": "Kolkata", "poona": "Pune"}
LANGUAGES = ["english", "hindi", "marathi", "tamil", "telugu", "kannada", "gujarati", "bengali", "hinglish"]
SEGMENTS = {"wealth": "Wealth", "priority": "Priority", "affluent": "Affluent", "mass": "Mass"}
UNIT = {"l": 1e5, "lakh": 1e5, "lakhs": 1e5, "lac": 1e5, "lacs": 1e5, "lpa": 1e5, "k": 1e3,
        "cr": 1e7, "crore": 1e7, "crores": 1e7, "m": 1e6, "mn": 1e6, "million": 1e6}

FIND_WORDS = re.compile(r"\b(find|identify|which|who|list|show|get|give|recommend|suggest|target|shortlist|search|top|best|prospects?|leads?|customers?)\b")
MSG_WORDS = re.compile(r"\b(message|messages|msg|outreach|whatsapp|email|e-mail|mail|sms|text|draft|write|rewrite|translate|pitch|copy)\b")
FOLLOW_UP = re.compile(r"\b(only|just|those|them|these|that list|same|instead|now|also|filter|narrow|exclude|remove|from them|among them|of them|out of)\b")
EXPLAIN = re.compile(r"\b(why|explain|reason|reasons|how come|justify)\b")
PROFILE = re.compile(r"\b(tell me about|profile|details? (?:of|for|about)|who is|look ?up|360|show me customer)\b")
EXPORT = re.compile(r"\b(export|download|csv|save (?:the )?(?:campaign|list|results)|push to crm)\b")
HELP = re.compile(r"^\s*(help|\?|what can you do|how do i use|commands)\b")
PRODUCTS_Q = re.compile(r"\b(what|which|list|show)\b.*\bproducts?\b|\bproduct catalog(?:ue)?\b")
CUSTOMER_ID = re.compile(r"\b(c\d{3,5})\b", re.I)


def _amount(num: str, unit: Optional[str]) -> float:
    value = float(num)
    if unit:
        return value * UNIT.get(unit.lower(), 1)
    return value * 1e5 if value < 1000 else value  # bare "20" in an income context means 20 lakh


class RuleBasedIntentParser:
    def __init__(self, products: dict, cities: list[str], known_first_names: list[str] | None = None):
        self.products = products
        self.cities = cities
        self.first_names = {n.lower() for n in (known_first_names or [])}
        self._aliases = sorted(((alias, pid) for pid, p in products.items() for alias in p["aliases"]),
                               key=lambda x: len(x[0]), reverse=True)

    # -- slot extractors ---------------------------------------------------------------
    def product(self, q: str) -> Optional[str]:
        for alias, pid in self._aliases:
            if re.search(rf"\b{re.escape(alias)}s?\b", q):
                return pid
        return None

    @staticmethod
    def channel(q: str) -> Optional[str]:
        if re.search(r"\b(whatsapp|wa|whats app)\b", q):
            return "whatsapp"
        if re.search(r"\b(email|e-mail|mail|emails)\b", q):
            return "email"
        if re.search(r"\b(sms|text message|texts)\b", q):
            return "sms"
        return None

    @staticmethod
    def language(q: str) -> Optional[str]:
        for lang in LANGUAGES:
            if re.search(rf"\b{lang}\b", q):
                return "Hindi" if lang == "hinglish" else lang.title()
        if re.search(r"\b(their|preferred|own|native|regional) language\b", q):
            return "preferred"
        return None

    @staticmethod
    def top_k(q: str) -> Optional[int]:
        m = re.search(r"\b(?:top|best|first)\s+(\d{1,3})\b", q) or re.search(r"\b(\d{1,3})\s+(?:customers|prospects|people|leads|names|clients)\b", q)
        if m:
            return int(m.group(1))
        words = {"three": 3, "five": 5, "ten": 10, "twenty": 20}
        m = re.search(r"\btop\s+(three|five|ten|twenty)\b", q)
        return words[m.group(1)] if m else None

    def filters(self, q: str) -> CustomerFilters:
        f = CustomerFilters()
        for city in self.cities:
            if re.search(rf"\b{city.lower()}\b", q):
                f.cities.append(city)
        for alias, city in CITY_ALIASES.items():
            if re.search(rf"\b{alias}\b", q) and city not in f.cities:
                f.cities.append(city)
        for word, seg in SEGMENTS.items():
            pattern = (rf"\b{word}\s+(?:segment|market|customers|clients|banking)\b" if word == "mass"
                       else rf"\b{word}\b(?!\s+(?:fund|creation|building))")
            if re.search(pattern, q):
                f.segments.append(seg)
        if re.search(r"\bsalaried\b", q):
            f.employment_types.append("salaried")
        if re.search(r"\b(self[- ]employed|business ?owners?|entrepreneurs?)\b", q):
            f.employment_types.append("self_employed")
        if re.search(r"\bretired|retirees|pensioners?\b", q):
            f.employment_types.append("retired")

        money = r"₹?\s*(\d+(?:\.\d+)?)\s*(lakhs?|lacs?|lpa|l|k|cr|crores?|m|mn|million)?\b"
        inc = r"(?:income|earning|earns|salary|ctc|package)"
        m = re.search(rf"{inc}[^\d₹]{{0,25}}(?:above|over|more than|greater than|>|>=|at least|min(?:imum)?)\s*{money}", q) or \
            re.search(rf"(?:above|over|more than|at least)\s*{money}\s*(?:annual |yearly )?{inc}", q)
        if m:
            f.min_income = _amount(m.group(1), m.group(2))
        m = re.search(rf"{inc}[^\d₹]{{0,25}}(?:below|under|less than|<|at most|max(?:imum)?)\s*{money}", q)
        if m:
            f.max_income = _amount(m.group(1), m.group(2))

        m = re.search(r"\b(?:aged?|age)\s*(?:between\s*)?(\d{2})\s*(?:-|to|and)\s*(\d{2})\b", q) or \
            re.search(r"\bbetween\s*(\d{2})\s*(?:and|-|to)\s*(\d{2})\s*(?:years|yrs|year olds)\b", q)
        if m:
            f.min_age, f.max_age = int(m.group(1)), int(m.group(2))
        else:
            m = re.search(r"\b(?:under|below|younger than|less than)\s*(\d{2})\s*(?:years|yrs|y/o|year[- ]olds?)?\b(?!\s*(?:l|lakh|k|cr))", q)
            if m and (re.search(r"\b(age|aged|years|yrs|year[- ]olds?|young)\b", q)):
                f.max_age = int(m.group(1))
            m = re.search(r"\b(?:over|above|older than)\s*(\d{2})\s*(?:years|yrs|year[- ]olds?)\b", q) or \
                re.search(r"\bage[d]?\s*(?:over|above|>=?|at least)\s*(\d{2})\b", q)
            if m:
                f.min_age = int(m.group(1))
        m = re.search(r"\b(?:credit score|cibil|bureau score)[^\d]{0,20}(\d{3})\b", q)
        if m:
            f.min_credit_score = int(m.group(1))
        return f

    def customer_ref(self, q_raw: str, state: ConversationState) -> Optional[str]:
        m = CUSTOMER_ID.search(q_raw)
        if m:
            return m.group(1).upper()
        low = q_raw.lower()
        for p in state.prospects:  # prefer names in the current shortlist
            if re.search(rf"\b{re.escape(p['full_name'].lower())}\b", low):
                return p["full_name"]
        for p in state.prospects:
            if re.search(rf"\b{re.escape(p['first_name'].lower())}\b", low):
                return p["first_name"]
        for token in re.findall(r"[A-Z][a-z]+(?:\s+[A-Z][a-z]+)?", q_raw):
            first = token.split()[0].lower()
            if first in self.first_names:
                return token
        return None

    # -- main ------------------------------------------------------------------------
    def parse(self, query: str, state: ConversationState) -> Intent:
        q = query.lower().strip()
        intent = Intent(raw_query=query, parser="rules")
        intent.product_id = self.product(q)
        intent.channel = self.channel(q)
        intent.language = self.language(q)  # may be the sentinel "preferred"
        intent.top_k = self.top_k(q)
        intent.filters = self.filters(q)
        intent.customer_ref = self.customer_ref(query, state)
        intent.generate_messages = bool(MSG_WORDS.search(q))
        if "this week" in q:
            intent.time_window = "this_week"
        has_slots = bool(intent.filters.describe() != "none" or intent.top_k or intent.product_id)

        if HELP.search(q):
            intent.type = IntentType.HELP
        elif EXPORT.search(q):
            intent.type = IntentType.EXPORT
        elif PRODUCTS_Q.search(q) and not re.search(r"\bcustomers?\b", q):
            intent.type = IntentType.LIST_PRODUCTS
        elif intent.customer_ref and EXPLAIN.search(q):
            intent.type = IntentType.EXPLAIN_CUSTOMER
        elif intent.customer_ref and (PROFILE.search(q) or not FIND_WORDS.search(q)) and not MSG_WORDS.search(q):
            intent.type = IntentType.CUSTOMER_PROFILE
        elif state.has_cohort() and intent.generate_messages and not has_slots and not re.search(r"\b(find|identify|search|shortlist)\b", q):
            intent.type = IntentType.GENERATE_MESSAGES
        elif state.search_intent and (FOLLOW_UP.search(q) or (has_slots and not re.search(r"\b(find|identify|search)\b", q))) \
                and not (intent.product_id and intent.product_id != state.product_id and re.search(r"\b(find|identify|which|who)\b", q)):
            intent.type = IntentType.REFINE
            intent.is_follow_up = True
        elif intent.product_id or FIND_WORDS.search(q):
            intent.type = IntentType.FIND_PROSPECTS
        else:
            intent.type = IntentType.UNKNOWN
        return intent


class LLMIntentParser:
    def __init__(self, llm: LLMClient, fallback: RuleBasedIntentParser):
        self.llm = llm
        self.fallback = fallback

    def parse(self, query: str, state: ConversationState) -> Intent:
        rules_intent = self.fallback.parse(query, state)
        if not self.llm.available:
            return rules_intent
        schema = json.dumps(Intent.model_json_schema(), separators=(",", ":"))
        system = INTENT_SYSTEM.format(schema=schema, products=", ".join(self.fallback.products),
                                      cities=", ".join(self.fallback.cities),
                                      context=json.dumps(state.context_summary(), default=str))
        try:
            data = parse_json_response(self.llm.complete(system, query, json_mode=True, max_tokens=500))
            data["raw_query"], data["parser"] = query, self.llm.name
            intent = Intent(**data)
        except (LLMError, ValidationError, TypeError, ValueError):
            return rules_intent
        # guardrails on LLM output: drop hallucinated ids / cities
        if intent.product_id not in self.fallback.products:
            intent.product_id = rules_intent.product_id
        intent.filters.cities = [c for c in intent.filters.cities if c in self.fallback.cities]
        if intent.type == IntentType.GENERATE_MESSAGES and not state.has_cohort():
            intent.type, intent.generate_messages = IntentType.FIND_PROSPECTS, True
        return intent
