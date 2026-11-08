from crm_agent.llm.base import NullLLM
from crm_agent.models import IntentType

MAIN = "Find high-value customers likely to convert for a personal loan this month and generate personalized WhatsApp messages."


def test_main_use_case(agent, settings):
    r = agent.chat(MAIN)
    tools = [e.tool for e in r.trace]
    assert tools == ["search_customers", "analyze_transactions", "score_customer_value", "check_product_eligibility",
                     "score_conversion_propensity", "recommend_products", "generate_outreach_messages",
                     "check_message_compliance", "export_campaign"]
    assert all(e.status == "ok" for e in r.trace)
    assert 0 < len(r.prospects) <= settings.default_top_k
    for p in r.prospects:  # every shortlisted customer satisfies the reasoning chain
        assert p["value_score"] >= settings.high_value_threshold
        assert p["propensity"] >= settings.min_propensity
        assert "personal_loan" not in p["existing_products"] and p["credit_score"] >= 700
        assert p["drivers"] and p["offer"]["amount"] > 0
    assert len(r.messages) == len(r.prospects)
    for m in r.messages:
        assert m.compliance_passed and m.deliverable
        c = next(p for p in r.prospects if p["customer_id"] == m.customer_id)
        assert c["first_name"] in m.body or c["last_name"] in m.body  # personalised greeting
    assert len({m.body for m in r.messages}) == len(r.messages)  # no two identical messages
    assert r.artifacts and r.artifacts[0].endswith(".csv")


def test_multi_turn_memory(agent):
    first = agent.chat(MAIN)
    refined = agent.chat("Only show the ones in Delhi")
    assert refined.intent.type == IntentType.REFINE
    assert all(p["city"] == "Delhi" for p in refined.prospects)
    assert {p["customer_id"] for p in refined.prospects} <= {p["customer_id"] for p in agent.ctx.repo.search_customers()}
    hindi = agent.chat("Rewrite the messages in Hindi")
    assert hindi.intent.type == IntentType.GENERATE_MESSAGES
    assert {m.customer_id for m in hindi.messages} == {p["customer_id"] for p in refined.prospects}
    assert all(m.language == "Hindi" for m in hindi.messages)
    email = agent.chat("Send them as email instead")
    # email where consented; otherwise the compliance tool re-routes to a consented channel
    assert all((m.channel == "email" and m.subject) or any("re-routed" in n for n in m.compliance_notes) for m in email.messages)
    assert any(m.channel == "email" for m in email.messages)
    name = refined.prospects[0]["full_name"]
    why = agent.chat(f"Why was {name} selected?")
    assert why.intent.type == IntentType.EXPLAIN_CUSTOMER and "Positive drivers" in why.text
    assert len(first.prospects) >= len(refined.prospects)


def test_reflection_relaxes_soft_thresholds(agent):
    agent.settings.high_value_threshold, original = 95.0, agent.settings.high_value_threshold  # nobody is this valuable
    try:
        r = agent.chat("Find personal loan prospects")
    finally:
        agent.settings.high_value_threshold = original
    reflections = [e for e in r.trace if e.tool == "reflection"]
    assert reflections and "relaxed" in reflections[0].summary
    assert any(e.status == "skipped" for e in r.trace)  # empty funnel short-circuits, no errors
    assert not any(e.status == "error" for e in r.trace)


def test_empty_funnel_never_errors(agent):
    r = agent.chat("Find personal loan prospects in Pune aged 80-90")
    assert not any(e.status == "error" for e in r.trace)
    assert "No customer met every criterion" in r.text


def test_profile_and_products(agent):
    r = agent.chat("Tell me about C0042")
    assert "C0042" in r.text and "Best-fit product" in r.text
    r = agent.chat("what products do we have?")
    assert "Personal Loan" in r.text


def test_results_depend_on_data_not_hardcoding(tmp_path, settings):
    """Re-seeding with a different random seed must change the shortlist."""
    from crm_agent.agent.orchestrator import CRMAgent
    from crm_agent.data.repository import CustomerRepository
    from crm_agent.data.seed import seed_database
    from tests.conftest import make_settings

    s2 = make_settings(tmp_path)
    seed_database(s2.db_path, 300, seed=999, as_of=settings.as_of_date)
    other = CRMAgent(settings=s2, llm=NullLLM(), repo=CustomerRepository(s2.db_path), persist=False)
    base = CRMAgent(settings=settings, llm=NullLLM(), persist=False)
    a = [p["full_name"] for p in base.chat(MAIN).prospects]
    b = [p["full_name"] for p in other.chat(MAIN).prospects]
    assert a != b
