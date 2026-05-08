"""Backward-compatible demo entry point.

The production pipeline lives in src.run / scheduler.runner. Keep this file as a
thin wrapper so older README snippets or local habits still work without carrying
a second copy of the pipeline logic.
"""
from src.research_agent.scheduler.runner import run_pipeline_from_config


def main() -> None:
    run_pipeline_from_config(trigger="manual")


if __name__ == "__main__":
    main()
