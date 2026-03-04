#!/usr/bin/env python3
"""检查数据库中所有论文的信息。"""
import sys
import os

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from sqlmodel import Session, select, col
from src.research_agent.storage.models import Paper, engine, create_db_and_tables


def main():
    create_db_and_tables()

    with Session(engine) as session:
        papers = session.exec(select(Paper).order_by(Paper.published_date.desc())).all()

    if not papers:
        print("Database is empty — no papers found.")
        return

    # ── Summary ──────────────────────────────────────
    total = len(papers)
    relevant = sum(1 for p in papers if p.is_relevant)
    analyzed = sum(1 for p in papers if p.analysis_report)
    bookmarked = sum(1 for p in papers if p.is_bookmarked)
    sources = {}
    for p in papers:
        sources[p.source] = sources.get(p.source, 0) + 1

    print("=" * 72)
    print(f"  DATABASE OVERVIEW  —  {total} papers")
    print("=" * 72)
    print(f"  Relevant: {relevant}  |  Analyzed: {analyzed}  |  Bookmarked: {bookmarked}")
    print(f"  Sources:  {', '.join(f'{k} ({v})' for k, v in sorted(sources.items()))}")
    print("=" * 72)
    print()

    # ── Per-paper detail ─────────────────────────────
    for i, p in enumerate(papers, 1):
        score_str = f"{p.relevance_score}/10" if p.relevance_score is not None else "N/A"
        relevant_str = "Yes" if p.is_relevant else ("No" if p.is_relevant is False else "Pending")
        has_report = "Yes" if p.analysis_report else "No"
        bookmark = " [Bookmarked]" if p.is_bookmarked else ""
        authors_str = ", ".join(p.authors[:3]) if p.authors else "Unknown"
        if p.authors and len(p.authors) > 3:
            authors_str += f" et al. ({len(p.authors)} total)"

        print(f"[{i}/{total}] {p.title[:90]}")
        print(f"  ID:        {p.id}")
        print(f"  Source:    {p.source}    Score: {score_str}    Relevant: {relevant_str}{bookmark}")
        print(f"  Date:      {p.published_date.strftime('%Y-%m-%d')}    DOI: {p.doi or '—'}")
        print(f"  Fetched:   {p.fetched_date.strftime('%Y-%m-%d') if p.fetched_date else '—'}")
        print(f"  Authors:   {authors_str}")
        print(f"  Report:    {has_report}    Download: {p.download_status}")
        print(f"  URL:       {p.url}")
        print(f"  Abstract:  {p.abstract[:120]}..." if len(p.abstract) > 120 else f"  Abstract:  {p.abstract}")
        print("-" * 72)
        break


if __name__ == "__main__":
    main()
