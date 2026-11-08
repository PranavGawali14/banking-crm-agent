"""Data-retrieval & analytics tools (customer search, profiles, transaction features)."""

from __future__ import annotations

import re
from datetime import timedelta
from typing import Any, Optional

from crm_agent.models import CustomerFilters, ToolResult
from crm_agent.scoring.features import compute_customer_features
from crm_agent.tools.base import Tool, ToolArgs, ToolContext

CUSTOMER_ID_RE = re.compile(r"^C\d{3,5}$", re.I)


class SearchCustomers(Tool):
    name = "search_customers"
    description = "Retrieve customers from the CRM database matching demographic/financial filters."

    class Args(ToolArgs):
        filters: CustomerFilters = CustomerFilters()
        limit: Optional[int] = None

    def run(self, ctx: ToolContext, args: Args) -> ToolResult:
        rows = ctx.repo.search_customers(args.filters, args.limit)
        total = ctx.repo.customer_count()
        return ToolResult(data=rows, halt=not rows,
                          summary=f"Retrieved {len(rows)} of {total} customers (filters: {args.filters.describe()})")


class GetCustomerProfile(Tool):
    name = "get_customer_profile"
    description = "Look up a single customer by id (e.g. C0042) or by name; prefers the current shortlist when names are ambiguous."

    class Args(ToolArgs):
        customer_ref: str
        candidates: Optional[list[dict[str, Any]]] = None

    def run(self, ctx: ToolContext, args: Args) -> ToolResult:
        ref = args.customer_ref.strip()
        if CUSTOMER_ID_RE.match(ref):
            c = ctx.repo.get_customer(ref)
            matches = [c] if c else []
        else:
            low = ref.lower()
            matches = [c for c in (args.candidates or [])
                       if low in (c["full_name"].lower(), c["first_name"].lower()) or low in c["full_name"].lower()]
            matches = (ctx.repo.get_customers([m["customer_id"] for m in matches]) if matches
                       else ctx.repo.find_customers_by_name(ref))
        if not matches:
            return ToolResult(ok=False, data=[], error=f"No customer found for '{ref}'", summary="customer not found")
        note = "" if len(matches) == 1 else f" – ambiguous, {len(matches)} matches"
        return ToolResult(data=matches, summary=f"Resolved '{ref}' → {', '.join(m['customer_id'] + ' ' + m['full_name'] for m in matches[:5])}{note}")


class AnalyzeTransactions(Tool):
    name = "analyze_transactions"
    description = ("Compute behavioural features from recent transactions and balances: income regularity, spend growth, "
                   "big-ticket life-event spends, balance dips, EMI burden, category mix.")

    class Args(ToolArgs):
        customers: list[dict[str, Any]]
        lookback_days: int = 90

    def run(self, ctx: ToolContext, args: Args) -> ToolResult:
        as_of = ctx.repo.as_of_date
        ids = [c["customer_id"] for c in args.customers]
        txns = ctx.repo.get_transactions(ids, as_of - timedelta(days=args.lookback_days))
        bals = ctx.repo.get_balance_snapshots(ids)
        feats = {c["customer_id"]: compute_customer_features(c, txns[c["customer_id"]], bals[c["customer_id"]], as_of, args.lookback_days)
                 for c in args.customers}
        n_txn = sum(len(v) for v in txns.values())
        events = sum(1 for f in feats.values() if f["summary"]["detected_life_event"])
        dips = sum(1 for f in feats.values() if f["model_features"]["balance_dip"] >= 0.25)
        return ToolResult(data=feats, summary=(f"Analysed {n_txn:,} transactions for {len(feats)} customers over {args.lookback_days} days "
                                               f"(as of {as_of}); {events} show big-ticket life-event spends, {dips} show a balance dip ≥25%"))
