"""缺陷分级能力（FR-040~042）。

确定性计算，全部走规则引擎；LLM 不参与数值判定（C1）。
"""
from __future__ import annotations

from app.engine.rule_engine import get_engine


def grade_defect(description: str, measurements: dict | None = None, device_type: str | None = None) -> dict:
    """判定缺陷等级，返回 {level, reasons, degraded}。"""
    return get_engine().grade_defect(description, measurements, device_type)


def deadline_for(level: str) -> dict:
    """等级 → 消缺时限（FR-041）。"""
    return get_engine().deadline_for(level)


def is_overdue(level: str, deadline_elapsed: bool) -> bool:
    """是否构成安全隐患（FR-042）：危急/严重超时未消缺。"""
    return level in ("危急", "严重") and deadline_elapsed
