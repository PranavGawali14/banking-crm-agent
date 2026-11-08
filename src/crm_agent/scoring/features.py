"""Feature engineering: turns raw customer + transaction data into behavioural signals.

The same normalisation helpers are used to build the (synthetic) training history and the
live features, so the propensity model sees identically-scaled inputs in both places.
"""

from __future__ import annotations

import math
from collections import defaultdict
from datetime import date, timedelta
from statistics import mean

LIFE_EVENT_CATEGORIES = ("wedding", "travel", "education", "medical", "home_improvement", "electronics")
DISCRETIONARY = ("groceries", "dining", "shopping", "fuel", "utilities", "medical_small", *LIFE_EVENT_CATEGORIES)
INCOME_CATEGORIES = ("salary", "business_income", "pension")

# Ordered feature vector consumed by the ML propensity model (matches campaign_history columns)
MODEL_FEATURES = [
    "credit_score_norm", "income_norm", "dti", "salaried", "salary_regularity", "spend_growth",
    "life_event_ratio", "balance_dip", "loan_page_visits_norm", "relationship_norm", "age_prime",
]

FEATURE_LABELS = {
    "credit_score_norm": "strong credit score",
    "income_norm": "high income",
    "dti": "low existing EMI burden",
    "salaried": "salaried employment",
    "salary_regularity": "regular salary credits",
    "spend_growth": "recent jump in spending",
    "life_event_ratio": "big-ticket life-event spending",
    "balance_dip": "recent dip in account balance",
    "loan_page_visits_norm": "browsed loan pages in the app",
    "relationship_norm": "long relationship with the bank",
    "age_prime": "prime borrowing age",
    "dining_spend": "frequent dining spends",
    "travel_spend": "regular travel spends",
    "shopping_spend": "high online shopping",
    "monthly_spend": "high monthly card/UPI spend",
    "rent_paid": "pays monthly rent",
    "income_level": "high income",
    "home_improvement_spend": "home-improvement purchases",
    "fuel_spend": "regular fuel spends",
    "idle_balance": "large idle balance",
    "age_senior": "senior citizen (bonus rate)",
    "age_young": "young professional",
    "low_spend_ratio": "saves a large share of income",
    "investment_spend": "already invests regularly",
    "life_event_spend": "big-ticket life-event spending",
    "loan_page_visits": "browsed loan pages in the app",
    "credit_score": "strong credit score",
    "relationship_years": "long relationship with the bank",
}


# Phrasing used when a feature *lowers* the score (customer is worse than average on it)
NEGATIVE_LABELS = {
    "credit_score_norm": "credit score below peers", "credit_score": "credit score below peers",
    "income_norm": "lower income than peers", "dti": "existing EMI burden",
    "salaried": "not salaried", "salary_regularity": "irregular income credits",
    "spend_growth": "spending flat or declining", "life_event_ratio": "no big-ticket spends recently",
    "balance_dip": "stable balance (no liquidity need)", "loan_page_visits_norm": "no loan-page browsing",
    "relationship_norm": "newer relationship", "age_prime": "outside prime borrowing age",
}


# --- normalisation helpers (shared with the data generator) -----------------------------
def clip(x: float, lo: float = 0.0, hi: float = 1.0) -> float:
    return max(lo, min(hi, x))


def norm_credit_score(score: float) -> float:
    return clip((score - 600) / 300)


def norm_income(annual_income: float) -> float:
    return clip((math.log(max(annual_income, 1)) - math.log(2e5)) / (math.log(5e6) - math.log(2e5)))


def norm_visits(visits: int) -> float:
    return clip(visits / 6)


def norm_relationship(years: float) -> float:
    return clip(years / 15)


def compute_customer_features(customer: dict, txns: list[dict], balances: list[dict], as_of: date,
                              lookback_days: int = 90) -> dict:
    income = float(customer["annual_income"])
    monthly_income = income / 12
    since = as_of - timedelta(days=lookback_days)
    last30 = as_of - timedelta(days=30)
    last45 = as_of - timedelta(days=45)
    months = max(1, round(lookback_days / 30))

    cat_spend: dict[str, float] = defaultdict(float)
    spend_last30 = spend_prior = 0.0
    income_months: set[int] = set()
    big_ticket: dict[str, float] = defaultdict(float)

    for t in txns:
        d = date.fromisoformat(t["txn_date"])
        if d < since or d > as_of:
            continue
        if t["direction"] == "credit":
            if t["category"] in INCOME_CATEGORIES:
                income_months.add(min(months - 1, (as_of - d).days // 30))  # 30-day bucket index
            continue
        cat_spend[t["category"]] += t["amount"]
        if t["category"] in DISCRETIONARY:
            if d >= last30:
                spend_last30 += t["amount"]
            else:
                spend_prior += t["amount"]
        # big-ticket = single debit ≥ 1% of annual income in a life-event category, last 45 days
        if t["category"] in LIFE_EVENT_CATEGORIES and d >= last45 and t["amount"] >= 0.01 * income:
            big_ticket[t["category"]] += t["amount"]

    prior_months = max(1, months - 1)
    prior_avg = spend_prior / prior_months
    spend_growth = clip((spend_last30 / prior_avg - 1) if prior_avg > 0 else 0.0, -1.0, 2.5)
    monthly_spend = (spend_last30 + spend_prior) / months

    big_ticket_total = sum(big_ticket.values())
    dominant_event = max(big_ticket, key=big_ticket.get) if big_ticket else None
    life_event_ratio = clip((big_ticket_total / income) / 0.35) if income else 0.0

    bal_values = [b["balance"] for b in balances]
    if len(bal_values) >= 3:
        earlier = mean(bal_values[:-2])
        balance_dip = clip((earlier - bal_values[-1]) / earlier) if earlier > 0 else 0.0
        avg_balance = mean(bal_values)
    else:
        balance_dip, avg_balance = 0.0, float(customer.get("avg_monthly_balance", 0))

    dti = clip(float(customer.get("existing_emi", 0)) * 12 / income if income else 1.0, 0, 2)
    salary_regularity = clip(len(income_months) / months)
    age = int(customer["age"])
    m = lambda cat: cat_spend.get(cat, 0.0) / months  # noqa: E731  monthly average

    model_features = {
        "credit_score_norm": norm_credit_score(customer["credit_score"]),
        "income_norm": norm_income(income),
        "dti": dti,
        "salaried": 1.0 if customer["employment_type"] == "salaried" else 0.0,
        "salary_regularity": salary_regularity,
        "spend_growth": spend_growth,
        "life_event_ratio": life_event_ratio,
        "balance_dip": balance_dip,
        "loan_page_visits_norm": norm_visits(int(customer.get("loan_page_visits_30d") or 0)),
        "relationship_norm": norm_relationship(float(customer["relationship_years"])),
        "age_prime": 1.0 if 25 <= age <= 45 else 0.0,
    }
    # 0..1 signals for the transparent heuristic scorer (product-specific weights in products.json)
    signals = {
        "life_event_spend": life_event_ratio,
        "spend_growth": clip(spend_growth / 2.5),
        "balance_dip": balance_dip,
        "loan_page_visits": model_features["loan_page_visits_norm"],
        "salary_regularity": salary_regularity,
        "credit_score": model_features["credit_score_norm"],
        "dti": clip(dti),
        "relationship_years": model_features["relationship_norm"],
        "dining_spend": clip(m("dining") / (0.08 * monthly_income)),
        "travel_spend": clip((m("travel") + big_ticket.get("travel", 0) / months) / (0.08 * monthly_income)),
        "shopping_spend": clip((m("shopping") + m("electronics")) / (0.12 * monthly_income)),
        "monthly_spend": clip(monthly_spend / (0.6 * monthly_income)),
        "rent_paid": clip(m("rent") / (0.2 * monthly_income)),
        "income_level": model_features["income_norm"],
        "home_improvement_spend": clip(big_ticket.get("home_improvement", 0) / (0.1 * income)),
        "fuel_spend": clip(m("fuel") / (0.08 * monthly_income)),
        "idle_balance": clip(avg_balance / (6 * max(monthly_spend, 1))),
        "age_senior": 1.0 if age >= 58 else 0.0,
        "age_young": 1.0 if age <= 35 else 0.0,
        "low_spend_ratio": 1 - clip(monthly_spend / monthly_income) if monthly_income else 0.0,
        "investment_spend": clip(m("investment") / (0.1 * monthly_income)),
    }
    top_categories = sorted(((k, v) for k, v in cat_spend.items() if k not in ("emi", "rent", "investment")),
                            key=lambda kv: kv[1], reverse=True)[:3]
    return {
        "customer_id": customer["customer_id"],
        "model_features": model_features,
        "signals": signals,
        "summary": {
            "monthly_income_est": round(monthly_income),
            "monthly_spend_avg": round(monthly_spend),
            "spend_last_30d": round(spend_last30),
            "spend_growth_pct": round(spend_growth * 100),
            "big_ticket_spend_45d": round(big_ticket_total),
            "detected_life_event": dominant_event,
            "balance_dip_pct": round(balance_dip * 100),
            "avg_balance": round(avg_balance),
            "dti_pct": round(dti * 100),
            "top_spend_categories": [k for k, _ in top_categories],
        },
    }
