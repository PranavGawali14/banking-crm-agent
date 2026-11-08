"""Indicative offer construction (amount / rate / EMI) from product rules + customer data."""

from __future__ import annotations


def emi(principal: float, annual_rate_pct: float, months: int) -> float:
    r = annual_rate_pct / 12 / 100
    if r == 0:
        return principal / months
    return principal * r * (1 + r) ** months / ((1 + r) ** months - 1)


def _rate_for(credit_score: int, table: list[list[float]]) -> float:
    for min_score, rate in table:
        if credit_score >= min_score:
            return rate
    return table[-1][1]


def build_offer(customer: dict, features: dict | None, product_cfg: dict) -> dict | None:
    o = product_cfg["offer"]
    income = customer["annual_income"]
    dti = (features or {}).get("model_features", {}).get("dti", 0.0)
    max_dti = product_cfg["eligibility"]["max_dti"] or 1.0

    if o["type"] == "loan":
        headroom = max(0.0, 1 - dti / max_dti)  # less headroom -> smaller offer
        amount = min(o["max_amount"], income * o["income_multiple"] * (0.5 + 0.5 * headroom))
        amount = int(amount // 10_000 * 10_000)
        if amount < o["min_amount"]:
            return None
        rate = _rate_for(customer["credit_score"], o["rate_by_credit_score"])
        tenure = 36 if 36 in o["tenure_months"] else o["tenure_months"][len(o["tenure_months"]) // 2]
        return {"type": "loan", "amount": amount, "rate": rate, "tenure_months": tenure,
                "emi": round(emi(amount, rate, tenure))}
    if o["type"] == "card":
        limit = int(min(o["max_amount"], max(o["min_amount"], income * o["credit_limit_income_multiple"])) // 10_000 * 10_000)
        return {"type": "card", "amount": limit}
    if o["type"] == "deposit":
        rate = o["rate"] + (o.get("senior_bonus", 0) if customer["age"] >= 58 else 0)
        return {"type": "deposit", "rate": rate, "amount": 0}
    if o["type"] == "investment":
        sip = max(o["min_sip"], int(income / 12 * 0.1 // 500 * 500))
        return {"type": "investment", "amount": sip}
    return None
