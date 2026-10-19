"""工单能力（FR-060~062）：草稿生成（写操作落库在 M4/M5 二次确认后）。"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from app.engine.rule_engine import get_engine


def create_workorder_draft(
    defect_level: str,
    content: str,
    device_id: str | None = None,
    assignee: str | None = None,
) -> dict:
    """生成工单草稿（未落库）。建议措施若由 LLM 生成须附来源，M4 接入 LLM 后强制。"""
    dl = get_engine().deadline_for(defect_level)
    now = datetime.now(timezone.utc)
    if "hours" in dl:
        deadline = now + timedelta(hours=dl["hours"])
    elif "days" in dl:
        deadline = now + timedelta(days=dl["days"])
    else:
        # 一般缺陷：列入年/季检修计划，无硬性时限；给季度计划兜底（90 天），
        # 避免落库时 deadline 为 None 违反 NOT NULL 约束。
        deadline = now + timedelta(days=90)

    draft = {
        "ref_type": "缺陷",
        "ref_id": device_id,
        "content": content,
        "level": defect_level,
        "deadline": deadline.isoformat() if deadline else None,
        "assignee": assignee,
        "status": "草稿",  # 待二次确认
    }
    return {"draft": draft, "message": "工单草稿已生成，待二次确认后落库"}
