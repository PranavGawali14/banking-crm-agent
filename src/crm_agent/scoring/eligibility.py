"""Hard eligibility / policy rules – deterministic by design.

Credit policy must be auditable, so these are rules (from config/products.json), never an LLM.
"""

from __future__ import annotations

from datetime import date


def check_eligibility(customer: dict, features: dict | None, product_id: str, product_cfg: dict,
                      as_of: date, cooldown_days: int = 30) -> dict:
    rules = product_cfg["eligibility"]
    fails: list[str] = []
    warnings: list[str] = []

    if not rules["min_age"] <= customer["age"] <= rules["max_age"]:
        fails.append(f"age {customer['age']} outside {rules['min_age']}-{rules['max_age']}")
    if customer["annual_income"] < rules["min_annual_income"]:
        fails.append(f"income ₹{customer['annual_income']/1e5:.1f}L below ₹{rules['min_annual_income']/1e5:.1f}L")
    if customer["credit_score"] < rules["min_credit_score"]:
        fails.append(f"credit score {customer['credit_score']} < {rules['min_credit_score']}")
    dti = (features or {}).get("model_features", {}).get("dti")
    if dti is None:
        dti = customer.get("existing_emi", 0) * 12 / max(customer["annual_income"], 1)
    if dti > rules["max_dti"]:
        fails.append(f"debt-to-income {dti:.0%} > {rules['max_dti']:.0%}")
    if customer["employment_type"] not in rules["employment_types"]:
        fails.append(f"employment type '{customer['employment_type']}' not eligible")
    held = set(customer.get("existing_products", []))
    for p in rules.get("exclude_if_holding", []):
        if p in held:
            fails.append(f"already holds {p.replace('_', ' ')}")
    if rules.get("requires_kyc") and customer.get("kyc_status") != "verified":
        fails.append("KYC not verified")
    if customer.get("dnd"):
        warnings.append("customer is on DND – only consented digital channels allowed")

    last = customer.get("last_contacted_date")
    if last and customer.get("last_contacted_product") == product_id:
        days = (as_of - date.fromisoformat(last)).days
        if days < cooldown_days:
            fails.append(f"already contacted for this product {days} days ago (cool-down {cooldown_days}d)")

    return {"eligible": not fails, "fail_reasons": fails, "warnings": warnings, "dti": round(dti, 3)}
