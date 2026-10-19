"""复盘案例提炼规则 + 历史查询辅助（纯逻辑，不需 DB/LLM）。

import 需要 sqlalchemy（repository 的顶层依赖），但不建立连接。
"""
from app.data.repository import _keyword_terms, _parse_dt
from app.skills.review_case import draft_from_workorder


def test_draft_from_workorder_with_diagnosis():
    wo = {"ref_id": "DEV1", "content": "变压器温度越限", "level": "严重"}
    diag = {"fault_type": "过热", "basis": ["温度=95℃", "上限=85℃"]}
    case = draft_from_workorder(wo, device_type="变压器", diagnosis=diag, session_id="s1")
    assert case["status"] == "草稿"
    assert case["version"] == "1.0.0"
    assert case["device_type"] == "变压器"
    assert case["symptom"] == "变压器温度越限"
    assert case["root_cause"] == "过热"
    assert case["basis_refs"] == ["温度=95℃", "上限=85℃"]
    assert case["action"] == ""  # 处置待人工补充
    assert case["source_ref_id"] == "DEV1"


def test_draft_from_workorder_no_diagnosis():
    wo = {"ref_id": "DEV2", "content": "开关柜异常"}
    case = draft_from_workorder(wo)
    assert case["root_cause"] is None  # 无诊断 → 待核实
    assert case["device_type"] == "通用"


def test_parse_dt():
    from datetime import datetime

    assert _parse_dt("2024-03-01T00:00:00") == datetime(2024, 3, 1)
    assert _parse_dt(None) is None
    assert _parse_dt("not-a-date") is None
    assert _parse_dt(datetime(2024, 3, 1)) == datetime(2024, 3, 1)


def test_keyword_terms():
    assert _keyword_terms("变压器 过热") == ["变压器", "过热"]
    assert _keyword_terms("  变压器   ") == ["变压器"]
    assert _keyword_terms("") == []
    assert _keyword_terms("Transformer Overheat") == ["transformer", "overheat"]
