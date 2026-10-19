"""三层记忆：工作记忆 / 会话状态 / 实体锚点。

- 工作记忆（多轮对话）：写穿 Redis 缓存 + PostgreSQL 持久化（Message 表），
  Redis 丢失 / 重启后从 PG 回读，保证多轮上下文不丢（SDD 4.1.6）。
- 会话状态 / 实体锚点：Redis；挂起态另由 RunCheckpoint 落 PG（见 engine/checkpoint.py）。
"""
from __future__ import annotations

import json

import redis

from app.config import get_settings


class Memory:
    def __init__(self, redis_url: str | None = None) -> None:
        self.redis_url = redis_url or get_settings().redis_url
        self._client: redis.Redis | None = None

    def _r(self) -> redis.Redis:
        if self._client is None:
            self._client = redis.Redis.from_url(self.redis_url, decode_responses=True)
        return self._client

    # ---- 工作记忆：最近 K 轮对话（Redis 缓存 + PG 持久化）----
    def get_history(self, session_id: str, k: int = 8) -> list[dict]:
        # 优先 Redis；命中空 / 不可用则回读 PG（扛 Redis 重启）
        try:
            raw = self._r().lrange(f"session:{session_id}:history", -k, -1)
            if raw:
                return [json.loads(x) for x in raw]
        except Exception:
            pass
        return self._durable_history(session_id, k)

    def append_history(self, session_id: str, role: str, content: str) -> None:
        # 写穿：先落 PG（durable），再写 Redis（缓存）
        self._durable_append(session_id, role, content)
        try:
            r = self._r()
            key = f"session:{session_id}:history"
            r.rpush(key, json.dumps({"role": role, "content": content}, ensure_ascii=False))
            r.ltrim(key, -20, -1)  # 只保留最近 20 轮，防超长
        except Exception:
            pass

    def _durable_history(self, session_id: str, k: int) -> list[dict]:
        try:
            from app.data import repository

            return repository.get_messages(session_id, k)
        except Exception:
            return []

    def _durable_append(self, session_id: str, role: str, content: str) -> None:
        try:
            from app.data import repository

            repository.append_message(session_id, role, content)
        except Exception:
            pass

    # ---- 会话状态：挂起态 / 意图 ----
    def get_state(self, session_id: str) -> dict:
        raw = self._r().get(f"session:{session_id}:state")
        return json.loads(raw) if raw else {}

    def set_state(self, session_id: str, state: dict) -> None:
        self._r().set(f"session:{session_id}:state", json.dumps(state, ensure_ascii=False))

    def clear_state(self, session_id: str) -> None:
        self._r().delete(f"session:{session_id}:state")

    # ---- 实体锚点：设备编号 / 缺陷等级等 ----
    def get_anchors(self, session_id: str) -> dict:
        raw = self._r().get(f"session:{session_id}:anchors")
        return json.loads(raw) if raw else {}

    def set_anchors(self, session_id: str, anchors: dict) -> None:
        self._r().set(f"session:{session_id}:anchors", json.dumps(anchors, ensure_ascii=False))
