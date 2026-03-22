"""
重新分析 analysis_report 中包含 API 错误信息的论文。
运行: python tools/reanalyze_failed.py [--dry-run] [--limit N] [--delay SECONDS]

Options:
  --dry-run    只列出需要重分析的论文，不实际执行
  --limit N    最多处理 N 篇论文（默认全部）
  --delay S    每篇论文之间等待秒数（默认 2s，避免触发频率限制）
"""

import sys
import os
import time
import argparse

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from sqlmodel import Session, select
from src.research_agent.storage.models import Paper, engine
from src.research_agent.agents.analysis.reviewer import PaperReviewer, ANALYSIS_MIN_SCORE
from loguru import logger

# 用于判定 analysis_report 是否为 API 错误的关键词
ERROR_KEYWORDS = [
    "LLM 分析出错",
    "LLM 汇总分析出错",
    "Error code: 429",
    "exceeded your current quota",
    "insufficient_quota",
    "rate_limit",
    "RateLimitError",
    "APIError",
    "Timeout",
    "Connection error",
]

# 一份正常的分析报告至少应该有这个长度
MIN_VALID_REPORT_LEN = 500


def find_failed_papers() -> list[Paper]:
    """找出所有 analysis_report 包含错误信息且评分达到分析阈值的论文"""
    with Session(engine) as session:
        papers = session.exec(
            select(Paper).where(
                Paper.analysis_report != None,
                Paper.relevance_score >= ANALYSIS_MIN_SCORE,
            )
        ).all()

        failed = []
        for p in papers:
            report = p.analysis_report or ""
            # 条件1: 报告很短且包含错误关键词
            if len(report) < MIN_VALID_REPORT_LEN and any(kw in report for kw in ERROR_KEYWORDS):
                failed.append(p)
        
        # 按来源分组退出 session 前先转为 list
        return failed


def get_paper_content_path(paper: Paper) -> tuple[str | None, str | None]:
    """
    确定论文的分析来源：PDF 路径 或 全文内容。
    返回 (pdf_path, full_text_content)
    """
    # 1. 检查 PDF 文件
    if paper.download_status == "downloaded":
        # arXiv 论文
        if paper.source == "arxiv":
            pdf_path = f"data/papers/{paper.id}.pdf".replace(":", "_")
            if os.path.exists(pdf_path):
                return pdf_path, None
        # 上传的论文
        elif paper.source == "uploaded_pdf":
            # uploaded:filename.pdf -> data/filename.pdf
            filename = paper.id.replace("uploaded:", "")
            for search_dir in ["data", "data/papers"]:
                pdf_path = os.path.join(search_dir, filename)
                if os.path.exists(pdf_path):
                    return pdf_path, None

    # 2. 检查数据库中的全文内容 (Elsevier 等)
    if paper.full_text_content:
        return None, paper.full_text_content

    return None, None


def reanalyze_papers(papers: list[Paper], delay: float = 2.0, dry_run: bool = False):
    """重新分析论文列表"""
    reviewer = PaperReviewer()

    success = 0
    skipped = 0
    failed = 0

    for i, paper in enumerate(papers):
        pdf_path, full_text = get_paper_content_path(paper)

        if not pdf_path and not full_text:
            logger.warning(f"  ⏭️  [{i+1}/{len(papers)}] 跳过 (无 PDF/全文): {paper.title[:60]}")
            skipped += 1
            continue

        source_desc = f"PDF: {pdf_path}" if pdf_path else f"全文: {len(full_text)} 字符"
        logger.info(f"  [{i+1}/{len(papers)}] {paper.title[:60]}")
        logger.info(f"    来源: {paper.source} | {source_desc}")

        if dry_run:
            logger.info(f"    🔍 [DRY RUN] 将重新分析")
            continue

        try:
            report = reviewer.analyze_paper(paper, pdf_path=pdf_path, full_content=full_text)

            if not report or len(report) < MIN_VALID_REPORT_LEN:
                logger.error(f"    ❌ 分析结果过短或为空 ({len(report) if report else 0} 字符)")
                failed += 1
                continue

            # 检查新报告是否还是错误信息
            if any(kw in report for kw in ERROR_KEYWORDS):
                logger.error(f"    ❌ 分析仍返回错误: {report[:150]}")
                failed += 1
                continue

            # 写入数据库
            with Session(engine) as session:
                db_paper = session.get(Paper, paper.id)
                if db_paper:
                    db_paper.analysis_report = report
                    session.add(db_paper)
                    session.commit()
                    logger.info(f"    ✅ 分析完成并已更新数据库 ({len(report)} 字符)")
                    success += 1

        except Exception as e:
            logger.error(f"    ❌ 分析出错: {e}")
            failed += 1

        # 延迟，避免触发 API 频率限制
        if i < len(papers) - 1 and not dry_run:
            time.sleep(delay)

    return success, failed, skipped


def main():
    parser = argparse.ArgumentParser(description="重新分析失败的论文")
    parser.add_argument("--dry-run", action="store_true", help="只列出需要重分析的论文")
    parser.add_argument("--limit", type=int, default=0, help="最多处理几篇 (0=全部)")
    parser.add_argument("--delay", type=float, default=2.0, help="每篇之间的延迟秒数")
    args = parser.parse_args()

    print("\n" + "=" * 64)
    print("  🔄  重新分析失败论文")
    print("=" * 64 + "\n")

    # 查找失败论文
    failed_papers = find_failed_papers()
    print(
        f"  发现 {len(failed_papers)} 篇论文的分析报告包含 API 错误信息"
        f"（且评分 >= {ANALYSIS_MIN_SCORE}）\n"
    )

    if not failed_papers:
        print("  ✅ 没有需要重新分析的论文！")
        return

    # 按来源统计
    sources = {}
    for p in failed_papers:
        sources[p.source] = sources.get(p.source, 0) + 1
    print(f"  来源分布: {sources}")

    # 限制数量
    if args.limit > 0:
        failed_papers = failed_papers[:args.limit]
        print(f"  本次处理: {len(failed_papers)} 篇 (--limit {args.limit})")

    if args.dry_run:
        print(f"\n  🔍 [DRY RUN 模式] 仅列出待处理论文:\n")

    print("-" * 64 + "\n")

    # 执行重分析
    success, failed, skipped = reanalyze_papers(
        failed_papers, delay=args.delay, dry_run=args.dry_run
    )

    # 汇总
    print("\n" + "=" * 64)
    if args.dry_run:
        analyzable = len(failed_papers) - skipped
        print(f"  🔍 [DRY RUN] 共 {len(failed_papers)} 篇，可分析 {analyzable} 篇，无 PDF/全文 {skipped} 篇")
    else:
        print(f"  ✅ 成功: {success}  ❌ 失败: {failed}  ⏭️  跳过: {skipped}  (共 {len(failed_papers)} 篇)")
    print("=" * 64 + "\n")


if __name__ == "__main__":
    main()
