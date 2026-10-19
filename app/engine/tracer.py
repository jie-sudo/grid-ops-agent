"""追溯器：会话 + 步骤调用链落库（FR-005 / NFR-005）。"""
from __future__ import annotations

import json
import uuid

from app.data import models
from app.data.database import get_write_session


def _json_safe(v):
    """把任意值转成 JSON 可序列化（datetime 等 fallback 到字符串）。"""
    return json.loads(json.dumps(v, ensure_ascii=False, default=str))


class Tracer:
    def start_session(self, user_id: str | None = None, intent: str | None = None) -> str:
        session_id = uuid.uuid4().hex
        with get_write_session() as s:
            s.add(models.Session(session_id=session_id, user_id=user_id, intent=intent))
            s.commit()
        return session_id

    def ensure_session(self, session_id: str, user_id: str | None = None) -> str:
        """确保 session 存在（前端可能传本地生成的 id，后端兜底补建）。"""
        with get_write_session() as s:
            if s.get(models.Session, session_id) is None:
                s.add(models.Session(session_id=session_id, user_id=user_id))
                s.commit()
        return session_id

    def record(
        self,
        session_id: str,
        step: int,
        tool: str | None = None,
        params: dict | None = None,
        result: dict | None = None,
        sources: list | None = None,
        elapsed_ms: int | None = None,
        degraded: bool = False,
    ) -> None:
        with get_write_session() as s:
            s.add(models.Trace(
                trace_id=uuid.uuid4().hex,
                session_id=session_id,
                step=step,
                tool=tool,
                params=_json_safe(params),
                result=_json_safe(result),
                sources=_json_safe(sources),
                elapsed_ms=elapsed_ms,
                degraded=degraded,
            ))
            s.commit()
