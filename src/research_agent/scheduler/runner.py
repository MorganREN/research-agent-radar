# src/research_agent/scheduler/runner.py
"""Config-driven pipeline runner.

Reads all parameters from user_config.yaml and executes:
  1. Scout phase  — discover papers from configured sources
  2. Filter phase — score relevance with LLM
  3. Download phase — fetch PDFs
  4. Analysis phase — generate deep reports
"""
import asyncio
from datetime import datetime
from pathlib import Path

import yaml
from loguru import logger
from sqlmodel import Session, select

from src.research_agent.storage.models import Paper, create_db_and_tables, engine
from src.research_agent.agents.scout.arxiv_scout import ArxivScout
from src.research_agent.agents.scout.elsevier_scout import ElsevierScout
from src.research_agent.agents.filter.triage_agent import RelevanceFilter
from src.research_agent.acquisition.downloader import DownloadManager
from src.research_agent.agents.analysis.reviewer import PaperReviewer
from src.research_agent.scheduler.status import create_run, complete_run, fail_run


CONFIG_PATH = Path(__file__).parent.parent / "config" / "user_config.yaml"


def _load_user_config() -> dict:
    """Load user_config.yaml."""
    if not CONFIG_PATH.exists():
        logger.warning(f"Config not found at {CONFIG_PATH}, using empty config")
        return {}
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def _build_arxiv_query(fields: list[str]) -> str:
    """Convert user research fields to an arXiv keyword query.

    Example: ["Artificial Intelligence", "Digital Twin"]
          -> 'all:"Artificial Intelligence" OR all:"Digital Twin"'
    """
    if not fields:
        return "cat:cs.AI"
    terms = [f'all:"{field}"' for field in fields]
    return " OR ".join(terms)


def _build_scouts(config: dict) -> list:
    """Instantiate scouts based on configured sources."""
    scouts = []
    sources = config.get("sources", ["arxiv"])
    fields = config.get("fields", [])

    if "arxiv" in sources:
        query = _build_arxiv_query(fields)
        days_back = config.get("arxiv_days_back", 7)
        scouts.append(ArxivScout(query=query, days_back=days_back))

    if "sciencedirect" in sources:
        scouts.append(ElsevierScout(
            max_results=30,
            year=datetime.now().year,
        ))

    return scouts


def _build_interests(fields: list[str]) -> str:
    """Build a numbered interests string from config fields."""
    if not fields:
        return "General computer science and engineering"
    return "\n".join(f"{i + 1}. {f}" for i, f in enumerate(fields))


def _run_ingestion(config: dict) -> tuple[int, int]:
    """Scout + filter + store. Returns (papers_found, papers_relevant)."""
    create_db_and_tables()

    scouts = _build_scouts(config)
    fields = config.get("fields", [])
    interests = _build_interests(fields)
    triage = RelevanceFilter(research_interests=interests)

    new_papers: list[Paper] = []
    for scout in scouts:
        try:
            new_papers += scout.fetch_papers()
        except Exception as e:
            logger.error(f"Scout {scout.__class__.__name__} failed: {e}")

    papers_found = len(new_papers)
    papers_relevant = 0

    with Session(engine) as session:
        for paper in new_papers:
            existing = session.get(Paper, paper.id)
            if existing:
                logger.info(f"Skipping existing paper: {paper.id}")
                continue

            logger.info(f"Evaluating relevance: {paper.title[:60]}...")
            result = triage.check_relevance(paper.title, paper.abstract)

            paper.is_relevant = result["is_relevant"]
            paper.relevance_reason = result["reason"]
            paper.relevance_score = result.get("relevance_score", 0)

            session.add(paper)
            session.commit()

            if paper.is_relevant:
                papers_relevant += 1
                logger.info(
                    f"  Relevant (score={paper.relevance_score}): {paper.title[:60]}"
                )
            else:
                logger.info(f"  Not relevant: {paper.title[:60]}")

    return papers_found, papers_relevant


async def _run_analysis_async() -> int:
    """Download + analyze relevant papers. Returns count of newly analyzed."""
    reviewer = PaperReviewer()
    downloader = DownloadManager()
    analyzed = 0

    with Session(engine) as session:
        papers = session.exec(
            select(Paper).where(Paper.is_relevant == True)
        ).all()

        for paper in papers:
            if paper.analysis_report:
                continue

            logger.info(f"Analyzing: {paper.id} ...")
            save_path = f"data/papers/{paper.id}.pdf".replace(":", "_")

            if paper.download_status != "downloaded":
                status = await downloader.process_download(
                    paper_id=paper.id,
                    url=paper.url,
                    source=paper.source,
                )
                if status != "downloaded":
                    logger.error(f"Download failed for {paper.id}, skipping.")
                    continue
                paper.download_status = status
                session.add(paper)
                session.commit()

            if paper.download_status == "downloaded":
                if paper.source == "arxiv":
                    report = reviewer.analyze_paper(paper, pdf_path=save_path)
                else:
                    report = reviewer.analyze_paper(
                        paper, full_content=paper.full_text_content
                    )
                paper.analysis_report = report
                session.add(paper)
                session.commit()
                analyzed += 1
                logger.success(f"Analysis complete: {paper.id}")

    return analyzed


def run_pipeline_from_config(trigger: str = "scheduled") -> None:
    """Full pipeline: scout -> filter -> download -> analyze.

    Reads all parameters from user_config.yaml.
    Logs execution to SchedulerRun table.
    """
    config = _load_user_config()
    run_record = create_run(trigger=trigger)

    try:
        logger.info("=== Pipeline started ===")

        # Phase 1: Ingestion (scout + filter)
        papers_found, papers_relevant = _run_ingestion(config)
        logger.info(
            f"Ingestion complete: {papers_found} found, {papers_relevant} relevant"
        )

        # Phase 2: Analysis (download + review)
        papers_analyzed = asyncio.run(_run_analysis_async())
        logger.info(f"Analysis complete: {papers_analyzed} papers analyzed")

        complete_run(
            run_record.id,
            papers_found=papers_found,
            papers_relevant=papers_relevant,
            papers_analyzed=papers_analyzed,
        )
        logger.info("=== Pipeline finished ===")

    except Exception as e:
        fail_run(run_record.id, str(e))
        logger.error(f"Pipeline failed: {e}")
        raise
