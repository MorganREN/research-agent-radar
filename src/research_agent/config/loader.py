"""Centralized configuration helpers for the research agent."""
from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml
from loguru import logger

CONFIG_DIR = Path(__file__).parent
USER_CONFIG_FILE = CONFIG_DIR / "user_config.yaml"
ANALYSIS_PROMPT_FILE = CONFIG_DIR / "analysis_prompt.yaml"

DEFAULT_USER_CONFIG: dict[str, Any] = {
    "fields": ["Artificial Intelligence", "Digital Twin", "Large Language Models"],
    "journals": ["Automation in Construction"],
    "sources": ["arxiv"],
    "scheduled_time": "05:00",
    "arxiv_days_back": 7,
}


def _read_yaml(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
        if not isinstance(data, dict):
            logger.warning(f"Config file {path} did not contain a mapping; ignoring it")
            return {}
        return data
    except Exception as e:
        logger.warning(f"Failed to read config file {path}: {e}")
        return {}


def _write_yaml(path: Path, data: dict[str, Any]) -> bool:
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            yaml.dump(data, f, default_flow_style=False, allow_unicode=True)
        return True
    except Exception as e:
        logger.error(f"Failed to write config file {path}: {e}")
        return False


def load_user_config(with_defaults: bool = True) -> dict[str, Any]:
    """Load user_config.yaml, optionally merged over safe defaults."""
    config = _read_yaml(USER_CONFIG_FILE)
    if not with_defaults:
        return config
    return {**DEFAULT_USER_CONFIG, **config}


def save_user_config(config: dict[str, Any]) -> bool:
    return _write_yaml(USER_CONFIG_FILE, config)


def user_config_exists() -> bool:
    return USER_CONFIG_FILE.exists()


def load_analysis_prompt() -> dict[str, Any]:
    return _read_yaml(ANALYSIS_PROMPT_FILE)


def save_analysis_prompt(prompt_data: dict[str, Any]) -> bool:
    return _write_yaml(ANALYSIS_PROMPT_FILE, prompt_data)
