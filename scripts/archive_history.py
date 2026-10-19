"""历史流水归档/清理（P0 保留策略）。

把超过 `history_retention_months` 的流水从热表挪到 `*_archive` 归档表
（`history_archive=true`，默认）或直接删除（`history_archive=false`）。
归档表由本脚本用 `CREATE TABLE ... (LIKE ... INCLUDING ALL)` 幂等建出。

用法：
    python scripts/archive_history.py [--months 36] [--archive/--no-archive] [--dry-run]
"""
from __future__ import annotations

import sys
from datetime import datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import text

from app.config import get_settings
from app.data.database import get_engine

# 表名 -> 主键列（归档幂等用 ON CONFLICT）
TABLES = {
    "message": "message_id",
    "trace": "trace_id",
    "evidence_record": "evidence_id",
    "budget_record": "record_id",
}


def cutoff_datetime(months: int) -> datetime:
    return datetime.now() - timedelta(days=months * 30)


def archive_table(engine, table: str, pk: str, cutoff: datetime, do_archive: bool, dry_run: bool) -> int:
    """把 table 中 created_at < cutoff 的行归档（或删除），返回处理行数。"""
    if dry_run:
        with engine.connect() as conn:
            n = conn.execute(
                text(f"SELECT count(*) FROM {table} WHERE created_at < :cutoff"),
                {"cutoff": cutoff},
            ).scalar()
        return int(n or 0)
    with engine.begin() as conn:
        if do_archive:
            conn.execute(text(f"CREATE TABLE IF NOT EXISTS {table}_archive (LIKE {table} INCLUDING ALL)"))
            conn.execute(
                text(
                    f"INSERT INTO {table}_archive SELECT * FROM {table} "
                    f"WHERE created_at < :cutoff ON CONFLICT ({pk}) DO NOTHING"
                ),
                {"cutoff": cutoff},
            )
        deleted = conn.execute(
            text(f"DELETE FROM {table} WHERE created_at < :cutoff"), {"cutoff": cutoff}
        ).rowcount
    return deleted


def main() -> None:
    import argparse

    s = get_settings()
    parser = argparse.ArgumentParser(description="归档/清理历史流水")
    parser.add_argument("--months", type=int, default=s.history_retention_months)
    parser.add_argument("--archive", dest="archive", action="store_true", default=s.history_archive)
    parser.add_argument("--no-archive", dest="archive", action="store_false")
    parser.add_argument("--dry-run", action="store_true", help="只统计不落库")
    args = parser.parse_args()

    engine = get_engine()
    cutoff = cutoff_datetime(args.months)
    print(f"cutoff = {cutoff.isoformat()}（{args.months} 个月），archive={args.archive}，dry_run={args.dry_run}")
    for table, pk in TABLES.items():
        n = archive_table(engine, table, pk, cutoff, args.archive, args.dry_run)
        print(f"  {table}: 处理 {n} 行")


if __name__ == "__main__":
    main()
