from crm_agent.data.seed import seed_database
from crm_agent.data.repository import CustomerRepository
from crm_agent.models import CustomerFilters
from crm_agent.scoring.features import MODEL_FEATURES, compute_customer_features
from datetime import timedelta


def test_seed_counts(repo):
    assert repo.customer_count() == 300
    assert len(repo.get_campaign_history("personal_loan")) == 3000


def test_seed_is_reproducible(tmp_path, settings):
    a = seed_database(tmp_path / "a.db", 50, seed=7, as_of=settings.as_of_date)
    b = seed_database(tmp_path / "b.db", 50, seed=7, as_of=settings.as_of_date)
    ra, rb = CustomerRepository(a), CustomerRepository(b)
    assert ra.search_customers() == rb.search_customers()


def test_search_filters(repo):
    rows = repo.search_customers(CustomerFilters(cities=["Pune"], min_income=1_000_000))
    assert rows and all(r["city"] == "Pune" and r["annual_income"] >= 1_000_000 for r in rows)


def test_features_bounded_and_detect_life_events(repo):
    customers = repo.search_customers()
    since = repo.as_of_date - timedelta(days=90)
    ids = [c["customer_id"] for c in customers]
    txns, bals = repo.get_transactions(ids, since), repo.get_balance_snapshots(ids)
    feats = [compute_customer_features(c, txns[c["customer_id"]], bals[c["customer_id"]], repo.as_of_date) for c in customers]
    for f in feats:
        for k in MODEL_FEATURES:
            assert -1.0 <= f["model_features"][k] <= 2.5
        assert all(0.0 <= v <= 1.0 for v in f["signals"].values())
    detected = [f for f in feats if f["summary"]["detected_life_event"]]
    assert 0.2 * len(feats) < len(detected) < 0.7 * len(feats)  # signals exist but are not universal
    # customers with a detected life event should, on average, show a bigger balance dip
    avg = lambda xs: sum(xs) / len(xs)  # noqa: E731
    others = [f for f in feats if not f["summary"]["detected_life_event"]]
    assert avg([f["model_features"]["balance_dip"] for f in detected]) > avg([f["model_features"]["balance_dip"] for f in others])
