#!/usr/bin/env python3
"""Delete all papers with a target relevance score.

Usage:
    python tools/delete_score_2_papers.py --score 2
    python tools/delete_score_2_papers.py --score 2 --dry-run
"""

import os
import sys
import argparse

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from loguru import logger
from sqlmodel import Session, select

from src.research_agent.storage.models import Paper, engine, create_db_and_tables


def delete_papers_by_score(
    target_score: int,
    dry_run: bool = False,
    preview_limit: int = 30,
) -> int:
    create_db_and_tables()

    with Session(engine) as session:
        target_papers = session.exec(
            select(Paper).where(Paper.relevance_score == target_score)
        ).all()

        total = len(target_papers)
        if total == 0:
            logger.info(f"No papers found with relevance_score == {target_score}.")
            return 0

        logger.info(f"Found {total} papers with relevance_score == {target_score}.")

        if dry_run:
            logger.warning("DRY-RUN mode: no rows will be deleted.")
            limit = max(0, preview_limit)
            for idx, paper in enumerate(target_papers[:limit], 1):
                logger.info(f"  [{idx}/{total}] {paper.id} | {paper.title[:80]}")
            hidden = total - min(total, limit)
            if hidden > 0:
                logger.info(f"  ... and {hidden} more (use --preview-limit to change)")
            return total

        for paper in target_papers:
            session.delete(paper)

        session.commit()
        logger.success(f"Deleted {total} papers with relevance_score == {target_score}.")
        return total


def delete_score_2_papers(dry_run: bool = False, preview_limit: int = 30) -> int:
    """Backward-compatible helper for the original score-2 cleanup script."""
    return delete_papers_by_score(2, dry_run=dry_run, preview_limit=preview_limit)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Delete all papers with a given relevance_score from the database."
    )
    parser.add_argument(
        "--score",
        type=int,
        default=2,
        help="Target relevance score to delete (default: 2).",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Preview which papers will be deleted without writing to DB.",
    )
    parser.add_argument(
        "--preview-limit",
        type=int,
        default=30,
        help="When --dry-run is used, show at most this many rows (default: 30).",
    )
    args = parser.parse_args()

    delete_papers_by_score(
        target_score=args.score,
        dry_run=args.dry_run,
        preview_limit=args.preview_limit,
    )


if __name__ == "__main__":
    main()
