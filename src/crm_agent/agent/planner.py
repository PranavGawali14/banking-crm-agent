"""Planner: structured ``Intent`` + conversation state → ordered, explainable ``Plan``.

Design choice: the *LLM understands* the request, but the *plan is assembled deterministically*
from a library of task recipes. In a regulated bank this gives reproducible, auditable runs
(same question → same tool sequence) while still handling free-form language. Each step carries
a human-readable ``description`` so the RM can see *why* the agent does what it does.
"""

from __future__ import annotations

from dataclasses import dataclass

from crm_agent.agent.state import ConversationState
from crm_agent.config import Settings
from crm_agent.models import Intent, IntentType, Plan, PlanStep

DEFAULT_PRODUCT = "personal_loan"


@dataclass
class Thresholds:
    high_value: float
    min_propensity: float


class Planner:
    def __init__(self, settings: Settings, products: dict):
        self.settings = settings
        self.products = products

    # -- intent resolution (merge follow-ups with memory) -------------------------------
    def resolve(self, intent: Intent, state: ConversationState) -> Intent:
        """Fill missing slots from conversation memory so follow-ups 'just work'."""
        r = intent.model_copy(deep=True)
        prev = state.search_intent
        if r.type == IntentType.REFINE and prev:
            r.filters = prev.filters.merged_with(intent.filters)
            r.product_id = intent.product_id or prev.product_id
            r.top_k = intent.top_k or prev.top_k
            r.generate_messages = intent.generate_messages or prev.generate_messages
            r.channel = intent.channel or prev.channel
            r.language = intent.language or prev.language
        if r.type in (IntentType.GENERATE_MESSAGES, IntentType.EXPLAIN_CUSTOMER, IntentType.EXPORT):
            r.product_id = r.product_id or state.product_id
            r.channel = r.channel or state.channel
            r.language = r.language or state.language
        r.product_id = r.product_id or DEFAULT_PRODUCT
        if r.generate_messages or r.type == IntentType.GENERATE_MESSAGES:
            r.channel = r.channel or "whatsapp"
        return r

    @staticmethod
    def _lang(intent: Intent) -> str | None:
        return None if intent.language in (None, "preferred") else intent.language

    # -- recipes ---------------------------------------------------------------------
    def build(self, intent: Intent, state: ConversationState, thresholds: Thresholds | None = None) -> Plan:
        t = thresholds or Thresholds(self.settings.high_value_threshold, self.settings.min_propensity)
        pname = self.products[intent.product_id]["name"]
        it = intent.type

        if it in (IntentType.FIND_PROSPECTS, IntentType.REFINE):
            top_k = intent.top_k or self.settings.default_top_k
            steps = [
                PlanStep(id="s1", tool="search_customers", output_key="customers", args={"filters": intent.filters},
                         description=f"Retrieve customers from CRM (filters: {intent.filters.describe()})"),
                PlanStep(id="s2", tool="analyze_transactions", output_key="features",
                         inputs={"customers": "customers"}, args={"lookback_days": self.settings.lookback_days},
                         description=f"Derive behavioural signals from the last {self.settings.lookback_days} days of transactions"),
                PlanStep(id="s3", tool="score_customer_value", output_key="high_value",
                         inputs={"customers": "customers", "features": "features"}, args={"min_score": t.high_value},
                         description=f"Keep high-value customers (value score ≥ {t.high_value:g})"),
                PlanStep(id="s4", tool="check_product_eligibility", output_key="eligibility",
                         inputs={"customers": "high_value", "features": "features"}, args={"product_id": intent.product_id},
                         description=f"Apply {pname} credit-policy & contact rules"),
                PlanStep(id="s5", tool="score_conversion_propensity", output_key="propensity",
                         inputs={"customers": "eligibility.eligible", "features": "features"},
                         args={"product_id": intent.product_id, "min_propensity": t.min_propensity, "top_k": top_k},
                         description=f"Estimate this month's conversion likelihood, keep ≥ {t.min_propensity:.0%}, rank top {top_k}"),
                PlanStep(id="s6", tool="recommend_products", output_key="prospects",
                         inputs={"customers": "propensity.ranked", "features": "features"},
                         args={"primary_product_id": intent.product_id},
                         description=f"Size an indicative {pname} offer and find the next-best cross-sell"),
            ]
            if intent.generate_messages:
                steps += self._message_steps(intent, start=7)
            goal = f"Find high-value customers likely to take a {pname} {intent.time_window.replace('_', ' ')}" + \
                   (f" and draft {intent.channel} outreach" if intent.generate_messages else "")
            return Plan(intent=intent, goal=goal, steps=steps)

        if it == IntentType.GENERATE_MESSAGES:
            return Plan(intent=intent, goal=f"Draft {intent.channel} messages for the current shortlist of {len(state.prospects)}",
                        steps=self._message_steps(intent, start=1))

        if it == IntentType.EXPLAIN_CUSTOMER:
            return Plan(intent=intent, goal=f"Explain the {pname} recommendation for {intent.customer_ref}", steps=[
                PlanStep(id="s1", tool="get_customer_profile", output_key="customers", inputs={"candidates": "state_prospects"},
                         args={"customer_ref": intent.customer_ref}, description=f"Resolve customer '{intent.customer_ref}'"),
                PlanStep(id="s2", tool="analyze_transactions", output_key="features", inputs={"customers": "customers"},
                         args={"lookback_days": self.settings.lookback_days}, description="Recompute behavioural signals"),
                PlanStep(id="s3", tool="score_customer_value", output_key="valued", inputs={"customers": "customers", "features": "features"},
                         description="Recompute value score and its components"),
                PlanStep(id="s4", tool="check_product_eligibility", output_key="eligibility",
                         inputs={"customers": "valued", "features": "features"}, args={"product_id": intent.product_id},
                         description=f"Re-check {pname} policy rules"),
                PlanStep(id="s5", tool="score_conversion_propensity", output_key="propensity",
                         inputs={"customers": "valued", "features": "features"}, args={"product_id": intent.product_id},
                         description="Recompute propensity with feature-level contributions"),
            ])

        if it == IntentType.CUSTOMER_PROFILE:
            return Plan(intent=intent, goal=f"Build a 360° view of {intent.customer_ref}", steps=[
                PlanStep(id="s1", tool="get_customer_profile", output_key="customers", inputs={"candidates": "state_prospects"},
                         args={"customer_ref": intent.customer_ref}, description=f"Resolve customer '{intent.customer_ref}'"),
                PlanStep(id="s2", tool="analyze_transactions", output_key="features", inputs={"customers": "customers"},
                         args={"lookback_days": self.settings.lookback_days}, description="Summarise recent financial behaviour"),
                PlanStep(id="s3", tool="score_customer_value", output_key="valued", inputs={"customers": "customers", "features": "features"},
                         description="Score customer value"),
                PlanStep(id="s4", tool="recommend_products", output_key="prospects", inputs={"customers": "valued", "features": "features"},
                         description="Recommend the best-fit products across the catalogue"),
            ])

        if it == IntentType.LIST_PRODUCTS:
            return Plan(intent=intent, goal="Show the product catalogue", steps=[
                PlanStep(id="s1", tool="list_products", output_key="products", description="Read product catalogue")])

        if it == IntentType.EXPORT:
            return Plan(intent=intent, goal="Export the current campaign", steps=[
                PlanStep(id="s1", tool="export_campaign", output_key="export",
                         inputs={"prospects": "state_prospects", "messages": "state_messages"},
                         args={"product_id": intent.product_id}, description="Write CSV/JSON for CRM upload")])

        return Plan(intent=intent, goal="Clarify the request", steps=[])

    def _message_steps(self, intent: Intent, start: int) -> list[PlanStep]:
        src = "prospects" if start > 1 else "state_prospects"
        lang = self._lang(intent)
        return [
            PlanStep(id=f"s{start}", tool="generate_outreach_messages", output_key="drafts", inputs={"prospects": src},
                     args={"product_id": intent.product_id, "channel": intent.channel, "language": lang},
                     description=f"Draft personalised {intent.channel} messages in {lang or 'each customer’s preferred language'}"),
            PlanStep(id=f"s{start+1}", tool="check_message_compliance", output_key="messages",
                     inputs={"messages": "drafts", "prospects": src}, args={"product_id": intent.product_id},
                     description="Validate consent, disclaimers, claims & PII; repair or re-route"),
            PlanStep(id=f"s{start+2}", tool="export_campaign", output_key="export",
                     inputs={"prospects": src, "messages": "messages"}, args={"product_id": intent.product_id},
                     description="Save CRM-ready campaign file"),
        ]
