import sys
from datetime import date
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from crm_agent.config import PROJECT_ROOT, Settings, override_settings  # noqa: E402
from crm_agent.data.repository import CustomerRepository  # noqa: E402
from crm_agent.data.seed import seed_database  # noqa: E402
from crm_agent.llm.base import NullLLM  # noqa: E402


def make_settings(tmp: Path) -> Settings:
    s = Settings()
    s.db_path = tmp / "crm.db"
    s.model_dir = tmp / "models"
    s.output_dir = tmp / "outputs"
    s.session_dir = tmp / "sessions"
    s.products_path = PROJECT_ROOT / "config" / "products.json"
    s.compliance_path = PROJECT_ROOT / "config" / "compliance_rules.json"
    s.as_of_date = date(2026, 11, 1)
    s.llm_provider = "none"
    return s


@pytest.fixture(scope="session")
def settings(tmp_path_factory):
    s = make_settings(tmp_path_factory.mktemp("crm"))
    override_settings(s)
    seed_database(s.db_path, num_customers=300, seed=42, as_of=s.as_of_date)
    return s


@pytest.fixture(scope="session")
def repo(settings):
    return CustomerRepository(settings.db_path)


@pytest.fixture()
def agent(settings, repo):
    from crm_agent.agent.orchestrator import CRMAgent

    return CRMAgent(settings=settings, llm=NullLLM(), repo=repo, persist=False)
