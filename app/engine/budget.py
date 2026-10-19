"""预算账本：预留式记账（借鉴 AegisOps `BudgetLedger`，适配同步单请求架构）。

核心原则：
- 每次模型调用前在账本内"预留"（请求数 + 估算 Token + 估算费用），用尽即抛
  `BudgetExceeded`，绝不在超限后继续调用；
- 调用后按供应商实际 usage 结算；供应商未返回 usage 时**保留预留量**，
  绝不当作零（宁高估、不低估）；
- 同步单请求场景下用进程内状态即可；持久化为 best-effort（新表未建 / 库
  不可用时不阻断），供审计与跨请求预算留痕。

费用为估算：`llm_price_rmb_per_mtok` 为每百万 token 综合单价（元），未配置
（=0）则不启用费用限额、只限请求数与 Token。
"""
from __future__ import annotations

import json
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone


class BudgetExceeded(RuntimeError):
    """预算耗尽（请求数 / Token / 费用任一超限）。"""


@dataclass
class BudgetState:
    """纯记账状态：预留 / 结算的算术独立于 DB，便于单测。"""

    max_requests: int
    max_tokens: int
    max_cost: float = 0.0  # 0 = 不限额
    requests: int = 0
    charged_tokens: int = 0
    charged_cost: float = 0.0

    def reserve(self, reserved_tokens: int, estimated_cost: float = 0.0) -> None:
        if self.requests >= self.max_requests:
            raise BudgetExceeded("模型调用次数达到上限")
        if self.charged_tokens + reserved_tokens > self.max_tokens:
            raise BudgetExceeded("Token 预算耗尽")
        if self.max_cost > 0 and self.charged_cost + estimated_cost > self.max_cost:
            raise BudgetExceeded("费用预算耗尽")
        self.requests += 1
        self.charged_tokens += reserved_tokens
        self.charged_cost += estimated_cost

    def reconcile(self, reserved_tokens: int, actual_tokens: int | None, actual_cost: float | None) -> None:
        """结算：把预留量换成实际量；未知则保留预留（不当作零）。"""
        if actual_tokens is not None:
            self.charged_tokens += actual_tokens - reserved_tokens
        if actual_cost is not None:
            self.charged_cost += actual_cost


class BudgetLedger:
    def __init__(self, run_id: str, settings=None, session_id: str = "") -> None:
        if settings is None:
            from app.config import get_settings

            settings = get_settings()
        self.settings = settings
        self.run_id = run_id
        self.session_id = session_id
        self.state = BudgetState(
            max_requests=settings.max_steps,
            max_tokens=settings.max_tokens_per_run,
            max_cost=settings.max_cost_per_run,
        )
        self._reserved: int | None = None  # 最近一次调用的预留 Token

    def reserve_tokens(self, payload) -> int:
        """保守预留：消息字节量 * 1.25 + 4096 余量 + 最大输出（AegisOps 同款思路）。"""
        n = len(json.dumps(payload, ensure_ascii=False, default=str).encode("utf-8"))
        return int(n * 1.25) + 4096 + int(self.settings.max_output_tokens)

    def estimated_cost(self, tokens: int) -> float:
        price = getattr(self.settings, "llm_price_rmb_per_mtok", 0.0) or 0.0
        if price <= 0:
            return 0.0
        return tokens / 1_000_000 * price

    def reserve(self, payload=None) -> None:
        reserved = self.reserve_tokens(payload) if payload else 4096
        self.state.reserve(reserved, self.estimated_cost(reserved))
        self._reserved = reserved
        self._persist("reserve")

    def reconcile(self, usage: dict | None) -> None:
        """按供应商 usage 结算；usage 缺字段时保留预留。"""
        actual_tokens = None
        actual_cost = None
        if usage:
            prompt = usage.get("prompt_tokens")
            completion = usage.get("completion_tokens")
            if prompt is not None and completion is not None:
                actual_tokens = int(prompt) + int(completion)
                price = getattr(self.settings, "llm_price_rmb_per_mtok", 0.0) or 0.0
                if price > 0:
                    actual_cost = actual_tokens / 1_000_000 * price
        self.state.reconcile(self._reserved or 0, actual_tokens, actual_cost)
        self._reserved = None
        self._persist("reconcile")

    def summary(self) -> dict:
        return {
            "requests": self.state.requests,
            "charged_tokens": self.state.charged_tokens,
            "charged_cost_rmb": round(self.state.charged_cost, 6),
            "max_requests": self.state.max_requests,
            "max_tokens": self.state.max_tokens,
            "max_cost_rmb": self.state.max_cost,
        }

    def _persist(self, event: str) -> None:
        """审计持久化（best-effort）。"""
        try:
            from app.data import models
            from app.data.database import get_write_session

            with get_write_session() as s:
                s.add(models.BudgetRecord(
                    record_id=uuid.uuid4().hex,
                    run_id=self.run_id,
                    session_id=self.session_id,
                    event=event,
                    requests=self.state.requests,
                    charged_tokens=self.state.charged_tokens,
                    charged_cost=self.state.charged_cost,
                ))
                s.commit()
        except Exception:
            pass
