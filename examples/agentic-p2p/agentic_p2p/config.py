"""Centralized configuration.

Never hard-code API keys or endpoints elsewhere in the codebase — everything
that varies between environments (ports, model names, credentials, service
URLs) is read here, once, from the environment (optionally loaded from a
local `.env` file via python-dotenv).
"""

from __future__ import annotations

import os
from dataclasses import dataclass

try:
    from dotenv import load_dotenv

    load_dotenv()
except ImportError:  # pragma: no cover - dotenv is a light optional convenience
    pass


def _get_int(name: str, default: int) -> int:
    raw = os.getenv(name)
    if raw is None or raw == "":
        return default
    try:
        return int(raw)
    except ValueError:
        return default


@dataclass(frozen=True)
class Settings:
    # Networking
    libp2p_port: int = _get_int("LIBP2P_PORT", 8000)
    peer_address: str = os.getenv("PEER_ADDRESS", "")

    # LLM (via LiteLLM)
    llm_model: str = os.getenv("LLM_MODEL", "gemini/gemini-3.6-flash")
    LLM_API_KEY = None
    llm_api_base: str = os.getenv("LLM_API_BASE", "")

    # EtherCalc
    ethercalc_url: str = os.getenv("ETHERCALC_URL", "http://localhost:8000")
    ethercalc_sheet: str = os.getenv("ETHERCALC_SHEET", "sales-analysis")

    # Misc
    log_level: str = os.getenv("LOG_LEVEL", "INFO")


def get_settings() -> Settings:
    """Return a fresh Settings snapshot from the current environment.

    Kept as a function (rather than a module-level singleton) so tests can
    monkeypatch os.environ and get an accurate reload.
    """
    return Settings()
