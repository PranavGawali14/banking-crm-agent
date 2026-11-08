import json

import pytest

from crm_agent.agent.intent import RuleBasedIntentParser
from crm_agent.agent.state import ConversationState
from crm_agent.models import Intent, IntentType


@pytest.fixture()
def parser(settings, repo):
    products = json.loads(settings.products_path.read_text())
    return RuleBasedIntentParser(products, repo.distinct_values("city"), ["Priya", "Kunal"])


def test_main_prompt(parser):
    i = parser.parse("Find high-value customers likely to convert for a personal loan this month and generate personalized WhatsApp messages.", ConversationState())
    assert i.type == IntentType.FIND_PROSPECTS and i.product_id == "personal_loan"
    assert i.channel == "whatsapp" and i.generate_messages


@pytest.mark.parametrize("q,check", [
    ("top 5 salaried customers in Bangalore with income above 20 lakh for a home loan",
     lambda i: i.top_k == 5 and i.filters.cities == ["Bengaluru"] and i.filters.min_income == 2_000_000
     and i.product_id == "home_loan" and i.filters.employment_types == ["salaried"]),
    ("credit card prospects aged 25-40 with cibil above 750",
     lambda i: (i.filters.min_age, i.filters.max_age, i.filters.min_credit_score) == (25, 40, 750) and i.product_id == "credit_card_premium"),
    ("find FD prospects among retirees", lambda i: i.product_id == "fixed_deposit" and i.filters.employment_types == ["retired"]),
    ("Tell me about C0042", lambda i: i.type == IntentType.CUSTOMER_PROFILE and i.customer_ref == "C0042"),
    ("what products do we have?", lambda i: i.type == IntentType.LIST_PRODUCTS),
    ("help", lambda i: i.type == IntentType.HELP),
])
def test_slots(parser, q, check):
    assert check(parser.parse(q, ConversationState()))


def test_follow_ups_use_memory(parser):
    st = ConversationState(search_intent=Intent(type=IntentType.FIND_PROSPECTS, product_id="personal_loan"), product_id="personal_loan",
                           prospects=[{"customer_id": "C0001", "full_name": "Priya Sharma", "first_name": "Priya"}])
    assert parser.parse("only the ones in Pune", st).type == IntentType.REFINE
    assert parser.parse("Rewrite the messages in Hindi", st).type == IntentType.GENERATE_MESSAGES
    assert parser.parse("Rewrite the messages in Hindi", st).language == "Hindi"
    i = parser.parse("why was Priya selected?", st)
    assert i.type == IntentType.EXPLAIN_CUSTOMER and i.customer_ref == "Priya"
    assert parser.parse("send them as email instead", st).channel == "email"
