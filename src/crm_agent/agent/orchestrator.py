"""The agent loop:  UNDERSTAND → RESOLVE (memory) → PLAN → EXECUTE → REFLECT → RESPOND → REMEMBER.

``CRMAgent.chat()`` is the single entry point used by the CLI, the Streamlit UI, the demo
script and the tests.
"""

from __future__ import annotations

from typing import Callable, Optional

from crm_agent.agent.executor import Executor
from crm_agent.agent.intent import LLMIntentParser, RuleBasedIntentParser
from crm_agent.agent.planner import Planner, Thresholds
from crm_agent.agent.responder import HELP_TEXT, Responder
from crm_agent.agent.state import ConversationState
from crm_agent.config import Settings, get_settings
from crm_agent.data.repository import CustomerRepository
from crm_agent.llm.base import LLMClient
from crm_agent.llm.providers import build_llm
from crm_agent.models import AgentResponse, IntentType, TraceEvent
from crm_agent.tools import ToolContext, default_registry

MAX_REFLECTIONS = 2


class CRMAgent:
    def __init__(self, settings: Settings | None = None, llm: LLMClient | None = None,
                 repo: CustomerRepository | None = None, session_id: str | None = None,
                 persist: bool = True, on_event: Optional[Callable[[TraceEvent], None]] = None):
        self.settings = settings or get_settings()
        self.llm = llm or build_llm(self.settings)
        self.ctx = ToolContext.build(self.settings, self.llm, repo)
        self.registry = default_registry()
        first_names = sorted({c["first_name"] for c in self.ctx.repo.search_customers()})
        rules = RuleBasedIntentParser(self.ctx.products, self.ctx.repo.distinct_values("city"), first_names)
        self.intent_parser = LLMIntentParser(self.llm, rules)
        self.planner = Planner(self.settings, self.ctx.products)
        self.executor = Executor(self.registry, self.ctx, on_event)
        self.responder = Responder(self.ctx.products, self.settings.lookback_days)
        self.persist = persist
        self.state = (ConversationState.load(self.settings.session_dir, session_id) if session_id else ConversationState())

    # ------------------------------------------------------------------------------------
    def chat(self, query: str) -> AgentResponse:
        self.state.add_turn("user", query)
        intent = self.intent_parser.parse(query, self.state)                       # 1. understand
        intent = self.planner.resolve(intent, self.state)                          # 2. resolve with memory

        if intent.type == IntentType.GENERATE_MESSAGES and not self.state.has_cohort():
            intent.type, intent.generate_messages = IntentType.FIND_PROSPECTS, True
        if intent.type in (IntentType.EXPLAIN_CUSTOMER, IntentType.CUSTOMER_PROFILE) and not intent.customer_ref:
            return self._reply(AgentResponse(text="Which customer do you mean? Give me a name or an id like `C0042`.", intent=intent))
        if intent.type in (IntentType.HELP, IntentType.UNKNOWN):
            prefix = "" if intent.type == IntentType.HELP else "I didn't quite get that.\n\n"
            return self._reply(AgentResponse(text=prefix + HELP_TEXT, intent=intent))

        thresholds = Thresholds(self.settings.high_value_threshold, self.settings.min_propensity)
        notes: list[str] = []
        trace: list[TraceEvent] = []
        for attempt in range(MAX_REFLECTIONS + 1):
            plan = self.planner.build(intent, self.state, thresholds)                 # 3. plan
            bb, step_trace, _ = self.executor.run(plan, self._blackboard())            # 4. execute
            if attempt:
                for ev in step_trace:
                    ev.step_id = f"r{attempt}.{ev.step_id}"
            trace += step_trace
            relaxed = self._reflect(intent, bb, step_trace, thresholds)                # 5. reflect
            if not relaxed or attempt == MAX_REFLECTIONS:
                break
            notes.append(relaxed)
            trace.append(TraceEvent(step_id=f"reflect{attempt + 1}", tool="reflection", status="info",
                                    description="Self-check on empty result", summary=relaxed))

        response = self.responder.respond(plan, bb, trace, notes, self.state)        # 6. respond
        self._remember(intent, bb, trace, response)                                   # 7. remember
        return self._reply(response)

    # ------------------------------------------------------------------------------------
    def _blackboard(self) -> dict:
        return {"state_prospects": self.state.prospects, "state_messages": self.state.messages,
                "state_features": self.state.features}

    def _reflect(self, intent, bb: dict, trace: list[TraceEvent], t: Thresholds) -> str | None:
        """If a prospect search came back empty, find the bottleneck stage and relax a *soft* threshold.

        Hard credit-policy rules are never relaxed – only the business heuristics (value cut-off,
        minimum propensity) are, and the RM is told exactly what changed.
        """
        if intent.type not in (IntentType.FIND_PROSPECTS, IntentType.REFINE):
            return None
        if any(e.status == "error" for e in trace) or bb.get("prospects"):
            return None
        if not bb.get("customers"):
            return None  # filters themselves match nobody – relaxing thresholds won't help
        if not bb.get("high_value") and t.high_value > 25:
            old = t.high_value
            t.high_value = max(25.0, t.high_value - 15)
            return f"No customers passed the high-value cut-off ({old:g}); relaxed it to {t.high_value:g} and re-ran the plan."
        if bb.get("eligibility", {}).get("eligible") and t.min_propensity > 0.1:
            old = t.min_propensity
            t.min_propensity = max(0.1, round(t.min_propensity - 0.15, 2))
            return f"No eligible customer reached {old:.0%} propensity; lowered the bar to {t.min_propensity:.0%} and re-ran the plan."
        return None

    def _remember(self, intent, bb: dict, trace, response: AgentResponse) -> None:
        s = self.state
        s.last_trace = trace
        if any(e.status == "error" for e in trace):
            return
        if intent.type in (IntentType.FIND_PROSPECTS, IntentType.REFINE):
            s.search_intent = intent
            s.product_id = intent.product_id
            s.prospects = bb.get("prospects", [])
            s.features = {p["customer_id"]: bb["features"][p["customer_id"]] for p in s.prospects if p["customer_id"] in bb.get("features", {})}
            s.messages = bb.get("messages", [])
            s.channel = intent.channel or s.channel
            s.language = intent.language
            s.funnel = {"scanned": len(bb.get("customers", [])), "high_value": len(bb.get("high_value", [])),
                        "eligible": len(bb.get("eligibility", {}).get("eligible", [])), "shortlisted": len(s.prospects)}
        elif intent.type == IntentType.GENERATE_MESSAGES:
            s.messages = bb.get("messages", [])
            s.channel, s.language = intent.channel, intent.language
            if s.search_intent:
                s.search_intent.generate_messages = True
                s.search_intent.channel, s.search_intent.language = intent.channel, intent.language
        s.artifacts += response.artifacts

    def _reply(self, response: AgentResponse) -> AgentResponse:
        self.state.add_turn("assistant", response.text[:500], response.intent.type.value if response.intent else None)
        if self.persist:
            self.state.save(self.settings.session_dir)
        return response

    def reset(self) -> None:
        self.state.reset()
