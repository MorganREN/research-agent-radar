#!/usr/bin/env python3
"""Project health check for local development and deployment."""
from __future__ import annotations

import importlib
import os
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.append(str(PROJECT_ROOT))

REQUIRED_MODULES = [
    "sqlmodel",
    "arxiv",
    "openai",
    "dotenv",
    "requests",
    "bs4",
    "pymupdf4llm",
    "streamlit",
    "loguru",
    "yaml",
    "plotly",
]

PROJECT_IMPORTS = [
    "src.run",
    "src.research_agent.config.loader",
    "src.research_agent.storage.models",
    "src.research_agent.scheduler.runner",
    "src.research_agent.agents.scout.arxiv_scout",
    "src.research_agent.agents.scout.elsevier_scout",
    "src.research_agent.agents.filter.triage_agent",
    "src.research_agent.agents.analysis.parser",
    "src.research_agent.agents.analysis.reviewer",
    "src.dashboard.database",
]


def _check_import(module_name: str) -> tuple[bool, str]:
    try:
        importlib.import_module(module_name)
        return True, "ok"
    except Exception as e:
        return False, str(e)


def main() -> int:
    print("Research Agent Radar doctor")
    print("=" * 64)
    print(f"Python: {sys.version.split()[0]}")
    print(f"Project root: {PROJECT_ROOT}")
    print()

    failures = 0

    print("Dependencies")
    for module_name in REQUIRED_MODULES:
        ok, detail = _check_import(module_name)
        marker = "OK" if ok else "FAIL"
        print(f"  {marker:<4} {module_name:<16} {detail}")
        failures += 0 if ok else 1

    print()
    print("Project imports")
    for module_name in PROJECT_IMPORTS:
        ok, detail = _check_import(module_name)
        marker = "OK" if ok else "FAIL"
        print(f"  {marker:<4} {module_name:<48} {detail}")
        failures += 0 if ok else 1

    print()
    print("Configuration")
    from src.research_agent.config.loader import USER_CONFIG_FILE, load_user_config

    config = load_user_config()
    print(f"  user_config: {USER_CONFIG_FILE} ({'exists' if USER_CONFIG_FILE.exists() else 'defaults'})")
    print(f"  sources: {config.get('sources', [])}")
    print(f"  fields: {len(config.get('fields', []))}")
    print(f"  journals: {len(config.get('journals', []))}")

    env_checks = {
        "KIMI_API_KEY": bool(os.getenv("KIMI_API_KEY")),
        "QWEN_API_KEY or BOB_API_KEY": bool(os.getenv("QWEN_API_KEY") or os.getenv("BOB_API_KEY")),
        "ELSEVIER_API_KEY": bool(os.getenv("ELSEVIER_API_KEY")),
    }
    for name, present in env_checks.items():
        marker = "OK" if present else "WARN"
        print(f"  {marker:<4} {name}")

    if failures:
        print()
        print(f"Doctor found {failures} import/dependency issue(s).")
        return 1

    print()
    print("Doctor passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
