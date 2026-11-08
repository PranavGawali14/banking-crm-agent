"""Synthetic banking data generator.

Creates a realistic, *reproducible* SQLite CRM database:

* ``customers``          – demographics, KYC, consent flags, product holdings, digital signals
* ``transactions``       – 6 months of credits/debits with categories and merchants
* ``balance_snapshots``  – month-end balances (used to detect liquidity dips)
* ``campaign_history``   – historical personal-loan campaign outcomes (training data for the
                           propensity model), generated from a hidden "ground-truth" behaviour model

Latent "life events" (wedding, travel, education, …) are planted in recent transactions so the
agent has real signals to discover – nothing about who is a good prospect is hard-coded in the
agent itself.

Run:  python -m crm_agent.data.seed  [--customers 300] [--seed 42]
"""

from __future__ import annotations

import argparse
import math
import random
import sqlite3
from datetime import date, timedelta
from pathlib import Path

from crm_agent.config import get_settings
from crm_agent.scoring.features import norm_credit_score, norm_income

FIRST_NAMES_M = ["Aarav", "Rohan", "Vikram", "Arjun", "Siddharth", "Rahul", "Karan", "Aditya", "Nikhil", "Amit",
                 "Suresh", "Rajesh", "Manoj", "Varun", "Kunal", "Harsh", "Pranav", "Yash", "Omkar", "Farhan",
                 "Imran", "Gaurav", "Sanjay", "Deepak", "Abhishek"]
FIRST_NAMES_F = ["Priya", "Ananya", "Sneha", "Pooja", "Kavya", "Neha", "Isha", "Riya", "Meera", "Shruti",
                 "Divya", "Aishwarya", "Tanvi", "Nisha", "Sakshi", "Aditi", "Swati", "Zoya", "Lakshmi", "Bhavna",
                 "Komal", "Radhika", "Shreya", "Anjali", "Fatima"]
LAST_NAMES = ["Sharma", "Patel", "Iyer", "Reddy", "Nair", "Kulkarni", "Deshpande", "Gupta", "Mehta", "Joshi",
              "Singh", "Khan", "Rao", "Menon", "Chatterjee", "Banerjee", "Agarwal", "Shah", "Pillai", "Verma",
              "Kapoor", "Bhat", "Shetty", "Pawar", "Das"]
CITIES = {  # city -> regional language
    "Mumbai": "Marathi", "Pune": "Marathi", "Bengaluru": "Kannada", "Delhi": "Hindi",
    "Hyderabad": "Telugu", "Chennai": "Tamil", "Ahmedabad": "Gujarati", "Kolkata": "Bengali",
}
OCCUPATIONS = {
    "salaried": ["Software Engineer", "Product Manager", "Doctor", "Chartered Accountant", "Teacher",
                 "Bank Officer", "Marketing Manager", "Data Analyst", "Consultant", "Civil Engineer"],
    "self_employed": ["Business Owner", "Retailer", "Architect", "Lawyer", "Restaurant Owner", "Trader"],
    "retired": ["Retired"],
    "student": ["Student"],
}
MERCHANTS = {
    "groceries": ["BigBasket", "DMart", "Reliance Fresh", "Nature's Basket"],
    "dining": ["Swiggy", "Zomato", "Barbeque Nation", "Starbucks", "Taj Restaurants"],
    "shopping": ["Amazon", "Myntra", "Flipkart", "Nykaa", "Lifestyle"],
    "fuel": ["Indian Oil", "HP Petrol", "Bharat Petroleum"],
    "utilities": ["Tata Power", "Airtel", "Jio", "Mahanagar Gas"],
    "rent": ["Rent Transfer"],
    "emi": ["Loan EMI"],
    "investment": ["SIP - Mutual Fund", "PPF Deposit", "NPS Contribution"],
    "medical_small": ["Apollo Pharmacy", "1mg", "PharmEasy"],
    # big-ticket life-event categories
    "wedding": ["Tanishq Jewellers", "Grand Banquets", "Shaadi Caterers", "Manyavar"],
    "travel": ["MakeMyTrip", "IndiGo Airlines", "Air India", "Taj Hotels", "Thomas Cook"],
    "education": ["University Fee Payment", "Coursera", "IELTS Registration", "Byju's"],
    "medical": ["Apollo Hospitals", "Fortis Healthcare", "Manipal Hospitals"],
    "home_improvement": ["Pepperfry", "IKEA", "Asian Paints", "Urban Ladder"],
    "electronics": ["Croma", "Apple Store", "Reliance Digital", "Vijay Sales"],
}
LIFE_EVENTS = ["wedding", "travel", "education", "medical", "home_improvement", "electronics"]

SCHEMA = """
DROP TABLE IF EXISTS customers;
DROP TABLE IF EXISTS transactions;
DROP TABLE IF EXISTS balance_snapshots;
DROP TABLE IF EXISTS campaign_history;

CREATE TABLE customers (
    customer_id TEXT PRIMARY KEY,
    first_name TEXT, last_name TEXT, full_name TEXT, gender TEXT, age INTEGER,
    city TEXT, preferred_language TEXT, occupation TEXT, employment_type TEXT,
    annual_income REAL, credit_score INTEGER, relationship_years REAL, segment TEXT,
    avg_monthly_balance REAL, existing_products TEXT, existing_emi REAL,
    kyc_status TEXT, whatsapp_opt_in INTEGER, sms_opt_in INTEGER, email_opt_in INTEGER, dnd INTEGER,
    email TEXT, phone_masked TEXT, preferred_channel TEXT,
    loan_page_visits_30d INTEGER, app_logins_30d INTEGER,
    last_contacted_date TEXT, last_contacted_product TEXT
);
CREATE TABLE transactions (
    txn_id TEXT PRIMARY KEY, customer_id TEXT, txn_date TEXT, amount REAL,
    direction TEXT, category TEXT, merchant TEXT, channel TEXT
);
CREATE INDEX idx_txn_customer_date ON transactions(customer_id, txn_date);
CREATE TABLE balance_snapshots (customer_id TEXT, month_end TEXT, balance REAL);
CREATE INDEX idx_bal_customer ON balance_snapshots(customer_id);
CREATE TABLE campaign_history (
    record_id INTEGER PRIMARY KEY, product_id TEXT, campaign_month TEXT,
    credit_score_norm REAL, income_norm REAL, dti REAL, salaried REAL, salary_regularity REAL,
    spend_growth REAL, life_event_ratio REAL, balance_dip REAL, loan_page_visits_norm REAL,
    relationship_norm REAL, age_prime REAL, converted INTEGER
);
"""


def _segment(income: float, balance: float) -> str:
    if income >= 5_000_000 or balance >= 2_500_000:
        return "Wealth"
    if income >= 2_500_000 or balance >= 1_000_000:
        return "Priority"
    if income >= 1_000_000 or balance >= 300_000:
        return "Affluent"
    return "Mass"


def _emi_for(product: str, income: float, rng: random.Random) -> float:
    monthly = income / 12
    return {
        "personal_loan": monthly * rng.uniform(0.08, 0.18),
        "home_loan": monthly * rng.uniform(0.20, 0.35),
        "auto_loan": monthly * rng.uniform(0.06, 0.12),
    }.get(product, 0.0)


def _make_customer(idx: int, rng: random.Random, as_of: date) -> dict:
    gender = rng.choice(["M", "F"])
    first = rng.choice(FIRST_NAMES_M if gender == "M" else FIRST_NAMES_F)
    last = rng.choice(LAST_NAMES)
    age = int(rng.triangular(21, 70, 33))
    city = rng.choice(list(CITIES))

    if age >= 60:
        employment = "retired" if rng.random() < 0.8 else "self_employed"
    elif age <= 23 and rng.random() < 0.5:
        employment = "student"
    else:
        employment = "salaried" if rng.random() < 0.72 else "self_employed"

    base = {"salaried": 1_100_000, "self_employed": 1_400_000, "retired": 500_000, "student": 150_000}[employment]
    income = round(base * math.exp(rng.gauss(0, 0.65)), -3)
    income = max(income, 120_000)
    credit = int(max(560, min(890, rng.gauss(735, 55))))
    rel_years = round(min(age - 18, rng.expovariate(1 / 5.5)), 1)
    balance = round(income * rng.uniform(0.03, 0.45) * (2.5 if employment == "retired" else 1), -2)

    products = ["savings_account"]
    for prod, p in [("credit_card_basic", 0.45), ("credit_card_premium", 0.12), ("personal_loan", 0.14),
                    ("home_loan", 0.16 if age > 28 else 0.03), ("auto_loan", 0.12),
                    ("fixed_deposit", 0.25), ("mutual_fund_sip", 0.22)]:
        if rng.random() < p:
            products.append(prod)
    emi = round(sum(_emi_for(p, income, rng) for p in products), -1)

    life_event = "none"
    if employment in ("salaried", "self_employed") and rng.random() < 0.45:
        life_event = rng.choice(LIFE_EVENTS)

    regional = CITIES[city]
    r = rng.random()
    language = "English" if r < 0.55 else ("Hindi" if r < 0.82 else regional)

    contacted, contacted_product = None, None
    if rng.random() < 0.18:
        contacted = (as_of - timedelta(days=rng.randint(3, 120))).isoformat()
        contacted_product = rng.choice(["personal_loan", "credit_card_premium", "fixed_deposit", "home_loan"])

    visits = 0
    if life_event != "none":
        visits = rng.choice([0, 1, 2, 3, 4, 6])
    elif rng.random() < 0.15:
        visits = rng.randint(1, 2)

    wa = rng.random() < 0.82
    return {
        "customer_id": f"C{idx:04d}",
        "first_name": first, "last_name": last, "full_name": f"{first} {last}",
        "gender": gender, "age": age, "city": city, "preferred_language": language,
        "occupation": rng.choice(OCCUPATIONS[employment]), "employment_type": employment,
        "annual_income": income, "credit_score": credit, "relationship_years": max(0.2, rel_years),
        "segment": _segment(income, balance), "avg_monthly_balance": balance,
        "existing_products": ",".join(products), "existing_emi": emi,
        "kyc_status": "verified" if rng.random() < 0.95 else "pending",
        "whatsapp_opt_in": int(wa), "sms_opt_in": int(rng.random() < 0.85),
        "email_opt_in": int(rng.random() < 0.75), "dnd": int(rng.random() < 0.07),
        "email": f"{first.lower()}.{last.lower()}{idx}@example.com",
        "phone_masked": f"+91-9XXXX-X{rng.randint(1000, 9999)}",
        "preferred_channel": "whatsapp" if wa and rng.random() < 0.7 else rng.choice(["email", "sms"]),
        "loan_page_visits_30d": visits, "app_logins_30d": rng.randint(0, 30),
        "last_contacted_date": contacted, "last_contacted_product": contacted_product,
        "_life_event": life_event,
    }


def _make_transactions(c: dict, rng: random.Random, as_of: date, months: int = 6):
    txns, n = [], 0
    monthly_income = c["annual_income"] / 12
    start = as_of - timedelta(days=months * 30)
    cid = c["customer_id"]
    products = c["existing_products"].split(",")
    pays_rent = "home_loan" not in products and rng.random() < 0.55 and c["employment_type"] != "retired"
    spend_ratio = rng.uniform(0.35, 0.7)

    def add(d: date, amount: float, direction: str, category: str, channel: str = "UPI"):
        nonlocal n
        n += 1
        merchant = rng.choice(MERCHANTS.get(category, ["Transfer"])) if category not in ("salary", "business_income", "pension", "interest") else {
            "salary": "Salary Credit", "business_income": "NEFT Business Receipt", "pension": "Pension Credit", "interest": "Interest Credit"}[category]
        txns.append((f"{cid}-T{n:05d}", cid, d.isoformat(), round(amount, 2), direction, category, merchant, channel))

    for m in range(months):
        month_start = start + timedelta(days=30 * m)
        # --- credits ---------------------------------------------------------------
        if c["employment_type"] == "salaried":
            # occasional missed/late salary for a few customers -> irregularity signal
            if rng.random() > 0.04:
                add(month_start + timedelta(days=rng.randint(0, 3)), monthly_income * rng.uniform(0.97, 1.03), "credit", "salary", "NEFT")
        elif c["employment_type"] == "self_employed":
            for _ in range(rng.randint(2, 6)):
                add(month_start + timedelta(days=rng.randint(0, 29)), monthly_income / 4 * rng.uniform(0.5, 1.6), "credit", "business_income", "NEFT")
        elif c["employment_type"] == "retired":
            add(month_start + timedelta(days=1), monthly_income * 0.9, "credit", "pension", "NEFT")
        else:
            add(month_start + timedelta(days=5), monthly_income, "credit", "salary", "UPI")
        # --- recurring debits ----------------------------------------------------------
        budget = monthly_income * spend_ratio
        if pays_rent:
            add(month_start + timedelta(days=rng.randint(1, 5)), monthly_income * rng.uniform(0.15, 0.25), "debit", "rent", "NEFT")
        if c["existing_emi"] > 0:
            add(month_start + timedelta(days=5), c["existing_emi"], "debit", "emi", "NACH")
        if "mutual_fund_sip" in products:
            add(month_start + timedelta(days=7), monthly_income * rng.uniform(0.05, 0.12), "debit", "investment", "NACH")
        for _ in range(rng.randint(2, 3)):
            add(month_start + timedelta(days=rng.randint(0, 29)), budget * 0.03 * rng.uniform(0.5, 1.5), "debit", "utilities", "NETBANKING")
        weights = {"groceries": 0.30, "dining": 0.18, "shopping": 0.22, "fuel": 0.12, "medical_small": 0.04, "travel": 0.06}
        for cat, w in weights.items():
            k = rng.randint(1, 5)
            for _ in range(k):
                add(month_start + timedelta(days=rng.randint(0, 29)), budget * w / k * rng.uniform(0.6, 1.4), "debit", cat, rng.choice(["UPI", "CARD", "CARD", "UPI"]))

    # --- life event: big-ticket spends concentrated in the last ~45 days ------------------
    if c["_life_event"] != "none":
        total = c["annual_income"] * rng.uniform(0.08, 0.35)
        parts = rng.randint(2, 4)
        for _ in range(parts):
            add(as_of - timedelta(days=rng.randint(1, 45)), total / parts * rng.uniform(0.7, 1.3), "debit", c["_life_event"], "CARD")
    return txns


def _make_balances(c: dict, rng: random.Random, as_of: date, months: int = 6):
    rows, bal = [], c["avg_monthly_balance"]
    for m in range(months, 0, -1):
        month_end = as_of - timedelta(days=30 * (m - 1))
        drift = rng.uniform(-0.08, 0.1)
        if c["_life_event"] != "none" and m <= 2:
            drift = rng.uniform(-0.45, -0.15)  # liquidity dip after large spends
        bal = max(1000.0, bal * (1 + drift))
        rows.append((c["customer_id"], month_end.isoformat(), round(bal, 2)))
    return rows


def _true_conversion_logit(x: dict) -> float:
    """Hidden ground-truth behaviour used ONLY to label synthetic history.

    The agent never sees this function; it must learn the relationship from data.
    """
    return (-5.0 + 3.0 * x["life_event_ratio"] + 1.3 * x["loan_page_visits_norm"] + 1.0 * x["balance_dip"]
            + 0.6 * max(0.0, x["spend_growth"]) + 1.0 * x["credit_score_norm"] + 0.6 * x["salary_regularity"]
            - 2.4 * x["dti"] + 0.5 * x["age_prime"] + 0.3 * x["relationship_norm"] + 0.3 * x["income_norm"])


def _make_campaign_history(rng: random.Random, as_of: date, n: int = 3000):
    rows = []
    for i in range(n):
        has_event = rng.random() < 0.4
        x = {
            "credit_score_norm": norm_credit_score(rng.gauss(735, 55)),
            "income_norm": norm_income(1.1e6 * math.exp(rng.gauss(0, 0.65))),
            "dti": min(0.9, max(0.0, rng.choice([0, 0, 0.1, 0.15, 0.25, 0.35]) + rng.uniform(-0.03, 0.08))),
            "salaried": 1.0 if rng.random() < 0.72 else 0.0,
            "salary_regularity": 1.0 if rng.random() < 0.8 else rng.uniform(0.3, 0.8),
            "spend_growth": (rng.uniform(0.2, 2.5) if has_event else rng.uniform(-0.4, 0.5)),
            "life_event_ratio": (min(1.0, rng.uniform(0.15, 0.95)) if has_event else rng.uniform(0, 0.05)),
            "balance_dip": (rng.uniform(0.2, 0.7) if has_event else max(0.0, rng.uniform(-0.1, 0.15))),
            "loan_page_visits_norm": (rng.choice([0, 0.17, 0.33, 0.5, 0.67, 1.0]) if has_event else rng.choice([0, 0, 0, 0.17])),
            "relationship_norm": min(1.0, rng.expovariate(1 / 5.5) / 15),
            "age_prime": 1.0 if rng.random() < 0.6 else 0.0,
        }
        p = 1 / (1 + math.exp(-_true_conversion_logit(x)))
        month = (as_of.replace(day=1) - timedelta(days=30 * rng.randint(1, 12))).strftime("%Y-%m")
        rows.append((i + 1, "personal_loan", month, *x.values(), int(rng.random() < p)))
    return rows


def seed_database(db_path: Path | None = None, num_customers: int | None = None, seed: int | None = None,
                  as_of: date | None = None) -> Path:
    settings = get_settings()
    db_path = Path(db_path or settings.db_path)
    num_customers = num_customers or settings.num_customers
    rng = random.Random(seed if seed is not None else settings.random_seed)
    as_of = as_of or settings.as_of_date
    db_path.parent.mkdir(parents=True, exist_ok=True)

    customers = [_make_customer(i + 1, rng, as_of) for i in range(num_customers)]
    txns, balances = [], []
    for c in customers:
        txns.extend(_make_transactions(c, rng, as_of))
        balances.extend(_make_balances(c, rng, as_of))
    history = _make_campaign_history(rng, as_of)

    cols = [k for k in customers[0] if not k.startswith("_")]
    with sqlite3.connect(db_path) as conn:
        conn.executescript(SCHEMA)
        conn.executemany(f"INSERT INTO customers ({','.join(cols)}) VALUES ({','.join('?' * len(cols))})",
                         [tuple(c[k] for k in cols) for c in customers])
        conn.executemany("INSERT INTO transactions VALUES (?,?,?,?,?,?,?,?)", txns)
        conn.executemany("INSERT INTO balance_snapshots VALUES (?,?,?)", balances)
        conn.executemany(f"INSERT INTO campaign_history VALUES ({','.join('?' * 15)})", history)
        conn.execute("CREATE TABLE IF NOT EXISTS meta (key TEXT PRIMARY KEY, value TEXT)")
        conn.execute("INSERT OR REPLACE INTO meta VALUES ('as_of_date', ?)", (as_of.isoformat(),))
    return db_path


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate the synthetic CRM database")
    parser.add_argument("--customers", type=int, default=None)
    parser.add_argument("--seed", type=int, default=None)
    parser.add_argument("--db", type=Path, default=None)
    args = parser.parse_args()
    path = seed_database(args.db, args.customers, args.seed)
    with sqlite3.connect(path) as conn:
        counts = {t: conn.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
                  for t in ("customers", "transactions", "balance_snapshots", "campaign_history")}
    print(f"Seeded {path}")
    for t, n in counts.items():
        print(f"  {t:<18} {n:>7,} rows")


if __name__ == "__main__":
    main()
