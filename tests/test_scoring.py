from crm_agent.scoring.eligibility import check_eligibility
from crm_agent.scoring.offers import build_offer, emi
from crm_agent.scoring.propensity import HeuristicPropensityModel, LogisticPropensityModel, explain
from crm_agent.scoring.value import score_value
import json


def _products(settings):
    return json.loads(settings.products_path.read_text())


def test_value_score_bounds(repo):
    for c in repo.search_customers():
        v = score_value(c)
        assert 0 <= v["value_score"] <= 100 and v["value_tier"] in {"Platinum", "Gold", "Silver", "Standard"}


def test_eligibility_rules(repo, settings):
    cfg = _products(settings)["personal_loan"]
    c = dict(repo.search_customers()[0], credit_score=650, existing_products=["savings_account", "personal_loan"], kyc_status="pending")
    res = check_eligibility(c, None, "personal_loan", cfg, repo.as_of_date)
    assert not res["eligible"]
    text = " ".join(res["fail_reasons"])
    assert "credit score" in text and "already holds" in text and "KYC" in text


def test_logistic_model_learns_signal(repo):
    m = LogisticPropensityModel("personal_loan").fit(repo.get_campaign_history("personal_loan"))
    assert m.metrics["test_auc"] > 0.75
    coef = m.coefficients()
    assert coef["life_event_ratio"] > 0 and coef["dti"] < 0  # recovered the hidden behaviour's direction


def test_heuristic_is_monotonic(settings):
    w = _products(settings)["personal_loan"]["signals"]
    model = HeuristicPropensityModel("personal_loan", w)
    low = {"signals": {k: 0.1 for k in w}}
    high = {"signals": {**{k: 0.9 for k in w}, "dti": 0.0}}
    assert model.predict(high)[0] > model.predict(low)[0]


def test_explain_labels():
    pos, neg = explain({"life_event_ratio": 1.2, "dti": -0.6, "age_prime": -0.3, "spend_growth": 0.4})
    assert pos[0] == "big-ticket life-event spending"
    assert "existing EMI burden" in neg and "outside prime borrowing age" in neg


def test_offer_and_emi(repo, settings):
    cfg = _products(settings)["personal_loan"]
    c = dict(repo.search_customers()[0], annual_income=1_200_000, credit_score=810)
    offer = build_offer(c, {"model_features": {"dti": 0.0}}, cfg)
    assert offer["amount"] == 1_440_000 and offer["rate"] == 10.49
    assert abs(emi(100000, 12, 12) - 8884.88) < 1
