"""Customer value scoring (who is a *high-value* customer?).

A transparent, weighted composite in the spirit of a CLV proxy. Each component is normalised
to 0..1 so the weights are directly interpretable and can be tuned by the business.
"""

from __future__ import annotations

import math

from crm_agent.scoring.features import clip, norm_income, norm_relationship

VALUE_WEIGHTS = {
    "income": 0.35,           # earning power
    "balance": 0.25,          # liabilities franchise (CASA)
    "relationship": 0.15,     # tenure / loyalty
    "product_depth": 0.10,    # cross-sell depth
    "engagement": 0.15,       # transaction velocity + digital engagement
}
TIERS = [(75, "Platinum"), (55, "Gold"), (35, "Silver"), (0, "Standard")]


def _log_norm(x: float, lo: float, hi: float) -> float:
    if x <= lo:
        return 0.0
    return clip(math.log(x / lo) / math.log(hi / lo))


def score_value(customer: dict, features: dict | None = None) -> dict:
    summary = (features or {}).get("summary", {})
    monthly_spend = summary.get("monthly_spend_avg", 0)
    avg_balance = summary.get("avg_balance", customer.get("avg_monthly_balance", 0))
    products = [p for p in customer.get("existing_products", []) if p != "savings_account"]

    components = {
        "income": norm_income(customer["annual_income"]),
        "balance": _log_norm(avg_balance, 10_000, 5_000_000),
        "relationship": norm_relationship(customer["relationship_years"]),
        "product_depth": clip(len(products) / 4),
        "engagement": 0.7 * _log_norm(monthly_spend, 5_000, 300_000) + 0.3 * clip((customer.get("app_logins_30d") or 0) / 20),
    }
    score = round(100 * sum(VALUE_WEIGHTS[k] * v for k, v in components.items()), 1)
    tier = next(name for threshold, name in TIERS if score >= threshold)
    return {"value_score": score, "value_tier": tier, "value_components": {k: round(v, 2) for k, v in components.items()}}
