"""中断恢复检查点 + 会话锁（借鉴 AegisOps checkpoint / lease，适配同步单请求架构）。

- CheckpointStore：把会话挂起态（待确认工单）与实体锚点落 PG；Redis 丢失 /
  进程重启后，下次请求可从 PG 恢复，避免"确认状态丢失 / 重复落库"。
- session_lock：同一会话的并发请求按 PG advisory lock 串行化（best-effort）。

持久化均为 best-effort：新表未建 / 库不可用时不阻断主流程；真正的"不重复
落库"由 repository.create_work_order 的 idempotency_key 保证（唯一约束兜底）。
"""
from __future__ import annotations

import contextlib


class CheckpointStore:
    """挂起态 / 锚点的 PG 检查点。"""

    def save(
        self,
        session_id: str,
        run_id: str,
        *,
        step: int = 0,
        intent: str | None = None,
        awaiting_confirm: bool = False,
        draft: dict | None = None,
        anchors: dict | None = None,
    ) -> None:
        try:
            from app.data import models
            from app.data.database import get_write_session

            with get_write_session() as s:
                row = s.get(models.RunCheckpoint, session_id)
                if row is None:
                    row = models.RunCheckpoint(session_id=session_id, run_id=run_id, step=step)
                    s.add(row)
                row.run_id = run_id
                row.step = step
                row.intent = intent
                row.awaiting_confirm = awaiting_confirm
                row.draft = draft
                row.anchors = anchors
                s.commit()
        except Exception:
            pass

    def load(self, session_id: str) -> dict | None:
        try:
            from app.data import models
            from app.data.database import get_write_session

            with get_write_session() as s:
                row = s.get(models.RunCheckpoint, session_id)
                if row is None:
                    return None
                return {
                    "session_id": row.session_id,
                    "run_id": row.run_id,
                    "step": row.step,
                    "intent": row.intent,
                    "awaiting_confirm": row.awaiting_confirm,
                    "draft": row.draft,
                    "anchors": row.anchors,
                }
        except Exception:
            return None

    def clear(self, session_id: str) -> None:
        try:
            from app.data import models
            from app.data.database import get_write_session

            with get_write_session() as s:
                row = s.get(models.RunCheckpoint, session_id)
                if row is not None:
                    s.delete(row)
                    s.commit()
        except Exception:
            pass


@contextlib.contextmanager
def session_lock(session_id: str):
    """会话级 advisory lock（best-effort）：库不可用时退化为无锁执行。

    用 Postgres `hashtext` 生成跨进程稳定的锁键（Python hash 每进程随机，
    不能用作锁键）；锁在同一连接上获取与释放。
    """
    conn = None
    acquired = False
    try:
        from sqlalchemy import text

        from app.data.database import get_write_engine

        conn = get_write_engine().connect()
        conn.execute(text("SELECT pg_advisory_lock(hashtext(:s))"), {"s": session_id})
        acquired = True
    except Exception:
        acquired = False
    try:
        yield
    finally:
        if acquired and conn is not None:
            try:
                from sqlalchemy import text

                conn.execute(text("SELECT pg_advisory_unlock(hashtext(:s))"), {"s": session_id})
            except Exception:
                pass
            finally:
                try:
                    conn.close()
                except Exception:
                    pass
