#!/usr/bin/env python3
# tools/rescore_papers.py
"""Re-score all existing papers in the database using the current interest list.

Usage:
    poetry run python tools/rescore_papers.py
        poetry run python tools/rescore_papers.py --workers 4
    poetry run python tools/rescore_papers.py --delete-irrelevant   # also remove 0-score papers
    poetry run python tools/rescore_papers.py --dry-run             # preview only, no DB writes

This script will:
  1. Load all papers from the database.
    2. Call RelevanceFilter.check_relevance() for each paper (supports multiprocessing).
    3. Batch update relevance_score, is_relevant, relevance_reason in the DB.
  4. Optionally delete papers that score 0 (--delete-irrelevant).
"""
import sys
import os
import argparse
import time
import multiprocessing as mp
from typing import Any

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from loguru import logger
from sqlmodel import Session, select

from src.research_agent.storage.models import Paper, engine, create_db_and_tables
from src.research_agent.agents.filter.triage_agent import RelevanceFilter


_WORKER_TRIAGE: RelevanceFilter | None = None
_WORKER_DELAY: float = 0.0


def _fmt_bar(current: int, total: int, width: int = 30) -> str:
    filled = int(width * current / max(1, total))
    bar = "█" * filled + "░" * (width - filled)
    pct = 100 * current // max(1, total)
    return f"[{bar}] {current}/{total} ({pct}%)"


def _init_worker(request_delay: float) -> None:
    global _WORKER_TRIAGE, _WORKER_DELAY
    _WORKER_TRIAGE = RelevanceFilter(research_interests="")
    _WORKER_DELAY = max(0.0, request_delay)


def _score_with_triage(
    triage: RelevanceFilter,
    paper_item: tuple[str, str, str | None, int | None],
    request_delay: float,
) -> dict[str, Any]:
    paper_id, title, abstract, old_score = paper_item
    try:
        result = triage.check_relevance(title, abstract or "")
        if request_delay > 0:
            time.sleep(request_delay)
        return {
            "paper_id": paper_id,
            "old_score": old_score,
            "ok": True,
            "new_score": int(result["relevance_score"]),
            "is_relevant": bool(result["is_relevant"]),
            "reason": str(result["reason"]),
        }
    except Exception as e:
        return {
            "paper_id": paper_id,
            "old_score": old_score,
            "ok": False,
            "error": str(e),
        }


def _score_one_mp(paper_item: tuple[str, str, str | None, int | None]) -> dict[str, Any]:
    global _WORKER_TRIAGE, _WORKER_DELAY
    if _WORKER_TRIAGE is None:
        _WORKER_TRIAGE = RelevanceFilter(research_interests="")
    return _score_with_triage(_WORKER_TRIAGE, paper_item, _WORKER_DELAY)


def _iter_scores(
    paper_items: list[tuple[str, str, str | None, int | None]],
    workers: int,
    request_delay: float,
):
    if workers <= 1:
        triage = RelevanceFilter(research_interests="")
        for item in paper_items:
            yield _score_with_triage(triage, item, request_delay)
        return

    ctx = mp.get_context("spawn")
    with ctx.Pool(
        processes=workers,
        initializer=_init_worker,
        initargs=(request_delay,),
    ) as pool:
        for result in pool.imap_unordered(_score_one_mp, paper_items, chunksize=1):
            yield result


def rescore(
    delete_irrelevant: bool = False,
    dry_run: bool = False,
    workers: int = 1,
    request_delay: float = 0.0,
) -> None:
    create_db_and_tables()

    with Session(engine) as session:
        papers: list[Paper] = list(session.exec(select(Paper)).all())

    if not papers:
        logger.info("No papers found in database, nothing to do.")
        return

    total = len(papers)
    workers = max(1, workers)
    paper_items = [(p.id, p.title, p.abstract, p.relevance_score) for p in papers]

    logger.info(f"Starting re-scoring for {total} papers...")
    triage_for_log = RelevanceFilter(research_interests="")
    logger.info(f"  Workers: {workers}")
    logger.info(f"  Request delay per worker: {request_delay:.2f}s")
    logger.info(f"  Research interests ({len(triage_for_log.interest_items)} items):")
    for i, item in enumerate(triage_for_log.interest_items, 1):
        logger.info(f"    {i}. {item}")
    if dry_run:
        logger.warning("DRY-RUN mode: no changes will be written to the database.")
    if delete_irrelevant:
        logger.warning("Papers scoring 0 (no matching interests) will be DELETED.")

    updated = 0
    deleted = 0
    errors = 0

    score_changes: list[tuple[str, int | None, int]] = []  # (id, old_score, new_score)
    updates_payload: dict[str, tuple[int, bool, str]] = {}
    results_by_id: dict[str, dict[str, Any]] = {}

    for idx, result in enumerate(_iter_scores(paper_items, workers=workers, request_delay=request_delay), 1):
        print(f"\r  {_fmt_bar(idx, total)}  ", end="", flush=True)
        paper_id = result["paper_id"]
        results_by_id[paper_id] = result

    for paper in papers:
        result = results_by_id.get(paper.id)
        if result is None:
            logger.error(f"  Missing score result for '{paper.title[:60]}'")
            errors += 1
            continue

        if not result.get("ok"):
            logger.error(f"  Error scoring '{paper.title[:60]}': {result.get('error', 'unknown error')}")
            errors += 1
            continue

        old_score = result["old_score"]
        new_score = result["new_score"]
        is_relevant = result["is_relevant"]
        reason = result["reason"]

        score_changes.append((paper.id, old_score, new_score))
        updates_payload[paper.id] = (new_score, is_relevant, reason)
        updated += 1

    if not dry_run and updates_payload:
        with Session(engine) as session:
            for paper_id, (new_score, is_relevant, reason) in updates_payload.items():
                db_paper = session.get(Paper, paper_id)
                if db_paper is None:
                    continue
                db_paper.relevance_score = new_score
                db_paper.is_relevant = is_relevant
                db_paper.relevance_reason = reason
                session.add(db_paper)

            if delete_irrelevant:
                for paper_id, (new_score, _, _) in updates_payload.items():
                    if new_score != 0:
                        continue
                    db_paper = session.get(Paper, paper_id)
                    if db_paper:
                        session.delete(db_paper)
                        deleted += 1

            session.commit()

    print()  # newline after progress bar

    if delete_irrelevant and not dry_run and deleted:
        logger.success(f"Deleted {deleted} irrelevant papers (score=0).")

    # Summary
    print()
    logger.success("=" * 60)
    logger.success(f"Re-score complete.")
    logger.success(f"  Papers processed : {updated}")
    logger.success(f"  Errors           : {errors}")
    if delete_irrelevant:
        logger.success(f"  Papers deleted   : {deleted}")
    if dry_run:
        logger.warning("  DRY-RUN — no DB changes persisted.")
    logger.success("=" * 60)

    # Print score change table
    print()
    print(f"{'Paper ID':<40}  {'Old':>4}  {'New':>4}  {'Change':>7}")
    print("-" * 60)
    for pid, old, new in score_changes:
        old_str = str(old) if old is not None else "N/A"
        delta = new - (old or 0)
        delta_str = f"+{delta}" if delta > 0 else str(delta)
        flag = " ⬆" if delta > 0 else (" ⬇" if delta < 0 else "  ")
        print(f"{pid:<40}  {old_str:>4}  {new:>4}  {delta_str:>7}{flag}")
    print()


def main():
    parser = argparse.ArgumentParser(
        description="Re-score all papers in the database using the current interest configuration."
    )
    parser.add_argument(
        "--delete-irrelevant",
        action="store_true",
        help="Delete papers that score 0 after re-scoring (no matching interests).",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Preview score changes without writing anything to the database.",
    )
    parser.add_argument(
        "--workers",
        type=int,
        default=max(1, min(4, os.cpu_count() or 1)),
        help="Number of worker processes for parallel LLM scoring (default: up to 4).",
    )
    parser.add_argument(
        "--request-delay",
        type=float,
        default=0.0,
        help="Delay in seconds after each score request in each worker (default: 0.0).",
    )
    args = parser.parse_args()
    rescore(
        delete_irrelevant=args.delete_irrelevant,
        dry_run=args.dry_run,
        workers=args.workers,
        request_delay=max(0.0, args.request_delay),
    )


if __name__ == "__main__":
    main()
