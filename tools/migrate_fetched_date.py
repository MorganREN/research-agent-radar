#!/usr/bin/env python3
"""迁移脚本：为已有论文补充 fetched_date 字段。

规则：
  - arxiv 来源 → fetched_date = published_date
  - 其他来源（elsevier、uploaded_pdf 等）→ fetched_date = 今天
  - 已有 fetched_date 的跳过

同时负责在 SQLite 表中添加 fetched_date 列（如果不存在）。

用法：python tools/migrate_fetched_date.py
"""
import sys
import os
import sqlite3
from datetime import datetime

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.research_agent.storage.models import sqlite_file_name


def main():
    db_path = sqlite_file_name
    if not os.path.exists(db_path):
        print(f"Database file not found: {db_path}")
        return

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # ── Step 1: 检查 fetched_date 列是否存在，不存在则添加 ──
    cursor.execute("PRAGMA table_info(paper)")
    columns = [row[1] for row in cursor.fetchall()]

    if "fetched_date" not in columns:
        print("Adding 'fetched_date' column to paper table...")
        cursor.execute("ALTER TABLE paper ADD COLUMN fetched_date TIMESTAMP")
        conn.commit()
        print("Column added.")
    else:
        print("'fetched_date' column already exists.")

    # ── Step 2: 回填已有论文 ──
    cursor.execute("SELECT id, source, published_date, fetched_date FROM paper")
    rows = cursor.fetchall()

    today_str = datetime.utcnow().isoformat()
    updated = 0
    skipped = 0

    for paper_id, source, published_date, fetched_date in rows:
        if fetched_date is not None:
            skipped += 1
            continue

        if source == "arxiv":
            new_value = published_date  # 已经是 ISO 格式字符串
        else:
            new_value = today_str

        cursor.execute(
            "UPDATE paper SET fetched_date = ? WHERE id = ?",
            (new_value, paper_id),
        )
        updated += 1

    conn.commit()
    conn.close()

    print(f"Migration complete: {updated} papers updated, {skipped} skipped (already had fetched_date).")


if __name__ == "__main__":
    main()
