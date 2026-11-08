"""Central configuration.

Every tunable (paths, thresholds, LLM provider, bank branding) lives here and can be
overridden through environment variables or a ``.env`` file. Nothing else in the code
base reads ``os.environ`` directly, which keeps components testable and swappable.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path

try:  # optional dependency
    from dotenv import load_dotenv

    load_dotenv()
except Exception:  # pragma: no cover
    pass

PROJECT_ROOT = Path(__file__).resolve().parents[2]


def _env(name: str, default: str) -> str:
    return os.getenv(name, default)


def _env_float(name: str, default: float) -> float:
    try:
        return float(os.getenv(name, default))
    except ValueError:
        return default


def _env_int(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, default))
    except ValueError:
        return default


@dataclass
class Settings:
    # --- storage -----------------------------------------------------------------
    db_path: Path = field(default_factory=lambda: Path(_env("CRM_DB_PATH", str(PROJECT_ROOT / "data" / "crm.db"))))
    products_path: Path = field(default_factory=lambda: PROJECT_ROOT / "config" / "products.json")
    compliance_path: Path = field(default_factory=lambda: PROJECT_ROOT / "config" / "compliance_rules.json")
    model_dir: Path = field(default_factory=lambda: PROJECT_ROOT / "models")
    output_dir: Path = field(default_factory=lambda: PROJECT_ROOT / "outputs")
    session_dir: Path = field(default_factory=lambda: PROJECT_ROOT / ".sessions")

    # --- synthetic data ------------------------------------------------------------
    num_customers: int = field(default_factory=lambda: _env_int("CRM_NUM_CUSTOMERS", 300))
    random_seed: int = field(default_factory=lambda: _env_int("CRM_SEED", 42))

    # --- business rules ------------------------------------------------------------
    as_of_date: date = field(default_factory=lambda: date.fromisoformat(_env("CRM_AS_OF_DATE", date.today().isoformat())))
    lookback_days: int = field(default_factory=lambda: _env_int("CRM_LOOKBACK_DAYS", 90))
    high_value_threshold: float = field(default_factory=lambda: _env_float("CRM_HIGH_VALUE_THRESHOLD", 55.0))
    min_propensity: float = field(default_factory=lambda: _env_float("CRM_MIN_PROPENSITY", 0.35))
    default_top_k: int = field(default_factory=lambda: _env_int("CRM_DEFAULT_TOP_K", 10))
    contact_cooldown_days: int = field(default_factory=lambda: _env_int("CRM_CONTACT_COOLDOWN_DAYS", 30))

    # --- LLM -----------------------------------------------------------------------
    # "auto" -> use whichever API key is present, else the offline rule engine.
    llm_provider: str = field(default_factory=lambda: _env("LLM_PROVIDER", "auto").lower())
    openai_model: str = field(default_factory=lambda: _env("OPENAI_MODEL", "gpt-4o-mini"))
    anthropic_model: str = field(default_factory=lambda: _env("ANTHROPIC_MODEL", "claude-sonnet-5-5"))
    llm_temperature: float = field(default_factory=lambda: _env_float("LLM_TEMPERATURE", 0.4))
    llm_timeout_s: float = field(default_factory=lambda: _env_float("LLM_TIMEOUT_S", 30.0))

    # --- branding --------------------------------------------------------------------
    bank_name: str = field(default_factory=lambda: _env("BANK_NAME", "NovaBank"))
    rm_name: str = field(default_factory=lambda: _env("RM_NAME", "Ananya Iyer"))
    rm_phone: str = field(default_factory=lambda: _env("RM_PHONE", "+91-98200-00000"))

    def ensure_dirs(self) -> None:
        for p in (self.db_path.parent, self.model_dir, self.output_dir, self.session_dir):
            p.mkdir(parents=True, exist_ok=True)


_settings: Settings | None = None


def get_settings() -> Settings:
    global _settings
    if _settings is None:
        _settings = Settings()
        _settings.ensure_dirs()
    return _settings


def override_settings(settings: Settings) -> None:
    """Used by tests to inject an isolated configuration."""
    global _settings
    _settings = settings
    _settings.ensure_dirs()
