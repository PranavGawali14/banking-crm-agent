"""LLM path tested with a fake client – no network or API key needed."""
import json

from crm_agent.agent.orchestrator import CRMAgent
from crm_agent.llm.base import LLMError
from crm_agent.models import IntentType


class FakeLLM:
    name = "fake-llm"
    available = True

    def __init__(self, unsafe=False, broken=False):
        self.unsafe, self.broken, self.calls = unsafe, broken, []

    def complete(self, system, user, json_mode=False, max_tokens=800):
        self.calls.append(system[:40])
        if self.broken:
            raise LLMError("boom")
        if "intent-understanding" in system:
            return json.dumps({"type": "find_prospects", "product_id": "personal_loan", "channel": "whatsapp",
                               "generate_messages": True, "top_k": 3, "filters": {"cities": ["Atlantis"]}})
        brief = json.loads(user.split("do NOT expose raw data):", 1)[1].split("Write the", 1)[0])
        if self.unsafe:
            return json.dumps({"body": f"Hi {brief['first_name']}, guaranteed approval, no documents!"})
        return json.dumps({"subject": None, "body": f"Hi {brief['first_name']} 👋 Your {brief['offer_headline']} is ready. Reply YES. "
                                                    f"T&C apply. Subject to credit approval. Reply STOP to opt out."})


def _agent(settings, repo, llm):
    return CRMAgent(settings=settings, llm=llm, repo=repo, persist=False)


def test_llm_intent_and_messages(settings, repo):
    llm = FakeLLM()
    r = _agent(settings, repo, llm).chat("get me 3 PL leads with WA drafts")
    assert r.intent.parser == "fake-llm" and r.intent.type == IntentType.FIND_PROSPECTS
    assert r.intent.filters.cities == []  # hallucinated city dropped by guardrail
    assert len(r.prospects) == 3
    assert all(m.generated_by == "fake-llm" or "re-routed" in " ".join(m.compliance_notes) for m in r.messages)
    assert all(m.compliance_passed for m in r.messages)


def test_unsafe_llm_output_is_regenerated(settings, repo):
    r = _agent(settings, repo, FakeLLM(unsafe=True)).chat("Find personal loan prospects and write WhatsApp messages")
    assert r.messages
    for m in r.messages:
        assert m.compliance_passed and "guaranteed" not in m.body.lower()
        assert any("regenerated" in n for n in m.compliance_notes)


def test_llm_outage_degrades_gracefully(settings, repo):
    r = _agent(settings, repo, FakeLLM(broken=True)).chat("Find personal loan prospects and write WhatsApp messages")
    assert r.intent.parser == "rules" and r.prospects
    assert all(m.generated_by == "template" for m in r.messages)
