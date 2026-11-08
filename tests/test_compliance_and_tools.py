import json

from crm_agent.models import OutreachMessage
from crm_agent.outreach.compliance import ComplianceChecker
from crm_agent.tools import default_registry


def _checker(settings):
    return ComplianceChecker(json.loads(settings.compliance_path.read_text()))


PROSPECT = {"customer_id": "C1", "whatsapp_opt_in": True, "sms_opt_in": True, "email_opt_in": True, "dnd": False}


def test_auto_adds_disclaimer_and_opt_out(settings):
    msg = OutreachMessage(customer_id="C1", customer_name="X", channel="whatsapp", language="English", body="Hi! Loan ready.")
    fixed, hard = _checker(settings).check(msg, PROSPECT, "lending")
    assert not hard and fixed.compliance_passed
    assert "T&C apply" in fixed.body and "Reply STOP" in fixed.body


def test_blocks_banned_claims_and_pii(settings):
    c = _checker(settings)
    bad = OutreachMessage(customer_id="C1", customer_name="X", channel="whatsapp", language="English",
                          body="Guaranteed approval! You spent Rs 50,000 at Croma from account 123456789012.")
    fixed, hard = c.check(bad, PROSPECT, "lending")
    assert hard and not fixed.compliance_passed
    assert any("banned" in n for n in fixed.compliance_notes) and any("PII" in n for n in fixed.compliance_notes)


def test_consent_and_dnd(settings):
    c = _checker(settings)
    p = dict(PROSPECT, whatsapp_opt_in=False, dnd=True)
    msg = OutreachMessage(customer_id="C1", customer_name="X", channel="whatsapp", language="English", body="Hi")
    fixed, _ = c.check(msg, p, "lending")
    assert not fixed.deliverable and fixed.fallback_channel == "email"
    assert not c.consent_ok(p, "sms")  # DND blocks SMS even with opt-in


def test_registry_exposes_json_schemas():
    reg = default_registry()
    schemas = reg.schemas()
    assert len(schemas) == 11
    for s in schemas:
        assert s["name"] and s["description"] and s["parameters"]["type"] == "object"


def test_tool_rejects_bad_args(agent):
    res = agent.registry.get("score_conversion_propensity")(agent.ctx, customers="oops")
    assert not res.ok and "invalid arguments" in res.error
    res = agent.registry.get("check_product_eligibility")(agent.ctx, customers=[], product_id="space_loan")
    assert not res.ok and "unknown product" in res.error
