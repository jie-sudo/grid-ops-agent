"""复盘案例能力（P1 长期记忆）：规则提炼 + 检索。

从已确认工单 + 会话内诊断结果做确定性规则提炼（不调用 LLM，符合 C1），
生成 status=草稿 的案例待人工审核；检索只返回「已审核且未废止」的当前版本。
"""
from __future__ import annotations

from app.data import repository


def draft_from_workorder(
    work_order: dict,
    *,
    device_type: str = "",
    diagnosis: dict | None = None,
    session_id: str = "",
) -> dict:
    """从工单 + 诊断结果规则提炼一条复盘案例草稿。

    - symptom = 工单 content
    - root_cause = 诊断 fault_type（未命中则 None → 待核实）
    - action 留空，待人工审核时补充
    - basis_refs = 诊断依据
    纯函数，不落库、不调 LLM。
    """
    symptom = (work_order.get("content") or "").strip()
    root_cause = None
    basis: list = []
    if diagnosis:
        root_cause = diagnosis.get("fault_type")
        basis = diagnosis.get("basis") or []
    title = symptom[:40] + "…" if len(symptom) > 40 else (symptom or "未命名案例")
    return {
        "title": title,
        "device_type": device_type or "通用",
        "symptom": symptom,
        "root_cause": root_cause,
        "action": "",  # 待人工补充
        "basis_refs": basis,
        "source_type": "工单",
        "source_ref_id": work_order.get("ref_id"),
        "session_id": session_id,
        "status": "草稿",
        "version": "1.0.0",
    }


def search_review_cases(query: str, device_type: str | None = None, limit: int = 8) -> dict:
    """检索已审核且未废止的历史处置案例（Agent 复用）。"""
    cases = repository.search_review_cases(query, device_type, limit)
    return {"cases": cases, "count": len(cases)}
