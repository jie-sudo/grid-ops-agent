"""数据库连接：管理 / 只读 / 读写三引擎，角色分离（只读保护的工程化落地）。

- 管理引擎（app 账号）：建表、建角色、灌数据
- 只读引擎（gridops_reader）：仅 SELECT + 事务只读，供查询路径
- 读写引擎（gridops_writer）：DML，仅供写路径（工单落库等）
"""
from __future__ import annotations

from sqlalchemy import Engine, create_engine, text
from sqlalchemy.orm import Session

from app.config import get_settings
from app.data.models import Base


def _engine(url: str) -> Engine:
    return create_engine(url, pool_pre_ping=True)


def get_engine() -> Engine:
    """管理引擎（建表 / 建角色 / 灌数据）。"""
    return _engine(get_settings().database_url)


def get_read_engine() -> Engine:
    """只读引擎：账号仅 SELECT 权限。"""
    return _engine(get_settings().database_url_read)


def get_write_engine() -> Engine:
    """读写引擎：DML 权限，仅供写路径。"""
    return _engine(get_settings().database_url_write)


def get_read_session() -> Session:
    return Session(get_read_engine())


def get_write_session() -> Session:
    return Session(get_write_engine())


def init_db(engine: Engine | None = None) -> None:
    """建表（试点级 create_all，生产建议 Alembic）。"""
    Base.metadata.create_all(engine or get_engine())


# 幂等迁移 DDL：create_all 只建新表，不改已有表的列/索引；这里补列 + 索引。
# 全部 IF NOT EXISTS，可重复执行。
MIGRATIONS = [
    # M7b：工单幂等键（列 + 唯一索引，防重复落库）
    "ALTER TABLE work_order ADD COLUMN IF NOT EXISTS idempotency_key VARCHAR(64)",
    "CREATE UNIQUE INDEX IF NOT EXISTS ux_work_order_idempotency_key ON work_order (idempotency_key)",
    # P0：历史流水 created_at 索引（日期检索）
    "CREATE INDEX IF NOT EXISTS ix_message_created_at ON message (created_at)",
    "CREATE INDEX IF NOT EXISTS ix_trace_created_at ON trace (created_at)",
    "CREATE INDEX IF NOT EXISTS ix_evidence_record_created_at ON evidence_record (created_at)",
    "CREATE INDEX IF NOT EXISTS ix_budget_record_created_at ON budget_record (created_at)",
]


def apply_migrations(engine: Engine | None = None) -> None:
    """执行幂等 DDL（补列 / 补索引）。需在建表之后调用。"""
    engine = engine or get_engine()
    with engine.begin() as conn:
        for stmt in MIGRATIONS:
            conn.execute(text(stmt))


def init_roles(engine: Engine | None = None) -> None:
    """创建只读/读写角色并授权（防御纵深）。

    - gridops_reader：仅 SELECT + 默认事务只读
    - gridops_writer：SELECT/INSERT/UPDATE/DELETE
    """
    engine = engine or get_engine()
    stmts = [
        "DO $$ BEGIN IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname='gridops_reader') "
        "THEN CREATE ROLE gridops_reader LOGIN PASSWORD 'reader'; END IF; END $$",
        "DO $$ BEGIN IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname='gridops_writer') "
        "THEN CREATE ROLE gridops_writer LOGIN PASSWORD 'writer'; END IF; END $$",
        "GRANT USAGE ON SCHEMA public TO gridops_reader, gridops_writer",
        "GRANT SELECT ON ALL TABLES IN SCHEMA public TO gridops_reader",
        "GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO gridops_writer",
        "ALTER ROLE gridops_reader SET default_transaction_read_only = on",
    ]
    with engine.begin() as conn:
        for stmt in stmts:
            conn.execute(text(stmt))


if __name__ == "__main__":
    init_db()
    apply_migrations()
    init_roles()
    print("建表 + 迁移 + 角色授权完成")
