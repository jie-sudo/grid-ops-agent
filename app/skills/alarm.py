"""告警分析能力（FR-030/031）。"""
from __future__ import annotations

from app.data.source import get_datasource

# 越限程度 → 等级；类型加成（过温/过流/局放默认不低于重要）
_SEVERE_TYPES = {"过温", "过流", "局放"}


def query_alarms(device_id: str | None = None, hours: int = 24) -> dict:
    alarms = get_datasource().query_alarms(device_id, hours)
    return {"alarms": alarms, "count": len(alarms)}


def alarm_level(alarm_type: str, over_ratio: float = 0.0) -> dict:
    """告警等级判定（FR-031）：按告警类型 + 越限程度。"""
    if over_ratio >= 0.5:
        level = "紧急"
    elif over_ratio >= 0.2:
        level = "重要"
    elif alarm_type in _SEVERE_TYPES:
        level = "重要"
    else:
        level = "提示"
    return {"level": level, "basis": f"类型[{alarm_type}]，越限比例={over_ratio:.0%}"}
