"""Typed contracts shared by every layer (agent, tools, interfaces).

Using Pydantic models as the contract between the LLM, the planner and the tools gives us
validation of LLM output for free and lets us export JSON-schemas for function calling.
"""

from __future__ import annotations

from enum import Enum
from typing import Any, Literal, Optional

from pydantic import BaseModel, Field

Channel = Literal["whatsapp", "sms", "email"]


class IntentType(str, Enum):
    FIND_PROSPECTS = "find_prospects"        # new prospecting request
    REFINE = "refine"                        # follow-up that narrows/changes the last search
    GENERATE_MESSAGES = "generate_messages"  # (re)write outreach for the current cohort
    EXPLAIN_CUSTOMER = "explain_customer"    # "why was Priya selected?"
    CUSTOMER_PROFILE = "customer_profile"    # "tell me about C0042"
    LIST_PRODUCTS = "list_products"
    EXPORT = "export"
    HELP = "help"
    UNKNOWN = "unknown"


class CustomerFilters(BaseModel):
    cities: list[str] = Field(default_factory=list)
    segments: list[str] = Field(default_factory=list, description="Mass | Affluent | Priority | Wealth")
    employment_types: list[str] = Field(default_factory=list, description="salaried | self_employed | retired | student")
    min_income: Optional[float] = Field(None, description="Annual income in INR")
    max_income: Optional[float] = None
    min_age: Optional[int] = None
    max_age: Optional[int] = None
    min_credit_score: Optional[int] = None

    def merged_with(self, newer: "CustomerFilters") -> "CustomerFilters":
        """Follow-up turns refine filters: any field set in ``newer`` wins."""
        data = self.model_dump()
        for key, value in newer.model_dump().items():
            if value not in (None, [], ""):
                data[key] = value
        return CustomerFilters(**data)

    def describe(self) -> str:
        parts = []
        if self.cities:
            parts.append("city in " + ", ".join(self.cities))
        if self.segments:
            parts.append("segment in " + ", ".join(self.segments))
        if self.employment_types:
            parts.append("employment " + ", ".join(self.employment_types))
        if self.min_income:
            parts.append(f"income ≥ ₹{self.min_income/1e5:.1f}L")
        if self.max_income:
            parts.append(f"income ≤ ₹{self.max_income/1e5:.1f}L")
        if self.min_age:
            parts.append(f"age ≥ {self.min_age}")
        if self.max_age:
            parts.append(f"age ≤ {self.max_age}")
        if self.min_credit_score:
            parts.append(f"credit score ≥ {self.min_credit_score}")
        return "; ".join(parts) or "none"


class Intent(BaseModel):
    type: IntentType = IntentType.UNKNOWN
    product_id: Optional[str] = Field(None, description="Key from config/products.json")
    channel: Optional[Channel] = None
    language: Optional[str] = Field(None, description="Language for outreach, e.g. English, Hindi, Marathi")
    top_k: Optional[int] = None
    filters: CustomerFilters = Field(default_factory=CustomerFilters)
    generate_messages: bool = False
    customer_ref: Optional[str] = Field(None, description="Customer id (C0001) or name the RM refers to")
    time_window: str = "this_month"
    is_follow_up: bool = False
    raw_query: str = ""
    parser: str = "rules"


class PlanStep(BaseModel):
    id: str
    tool: str
    description: str
    args: dict[str, Any] = Field(default_factory=dict)
    # arg_name -> blackboard key; resolved by the executor right before the call
    inputs: dict[str, str] = Field(default_factory=dict)
    output_key: Optional[str] = None


class Plan(BaseModel):
    intent: Intent
    goal: str
    steps: list[PlanStep] = Field(default_factory=list)


class ToolResult(BaseModel):
    ok: bool = True
    data: Any = None
    summary: str = ""
    error: Optional[str] = None
    halt: bool = False  # "nothing left to act on" – remaining steps are skipped (not an error)


class TraceEvent(BaseModel):
    step_id: str
    tool: str
    description: str
    status: Literal["ok", "error", "skipped", "info"] = "ok"
    summary: str = ""
    duration_ms: float = 0.0


class OutreachMessage(BaseModel):
    customer_id: str
    customer_name: str
    channel: Channel
    language: str
    body: str
    subject: Optional[str] = None
    generated_by: str = "template"
    compliance_passed: bool = False
    compliance_notes: list[str] = Field(default_factory=list)
    deliverable: bool = True
    fallback_channel: Optional[Channel] = None


class AgentResponse(BaseModel):
    text: str
    intent: Optional[Intent] = None
    plan: Optional[Plan] = None
    trace: list[TraceEvent] = Field(default_factory=list)
    prospects: list[dict[str, Any]] = Field(default_factory=list)
    messages: list[OutreachMessage] = Field(default_factory=list)
    artifacts: list[str] = Field(default_factory=list)
