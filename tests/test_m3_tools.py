"""M3 验收：工具可独立调用、返回结构化结果。"""
from app.engine.tools import get_tool, list_tools
from app.tools import register_all_tools

register_all_tools()


def test_tools_registered():
    names = {t.name for t in list_tools()}
    assert {
        "retrieve_knowledge", "query_device", "query_measurements", "query_state",
        "query_alarms", "alarm_level", "grade_defect", "diagnose",
        "create_workorder_draft", "deadline_for",
    } <= names


def test_alarm_level():
    assert get_tool("alarm_level").handler("过温", 0.6)["level"] == "紧急"
    assert get_tool("alarm_level").handler("过温", 0.0)["level"] == "重要"
    assert get_tool("alarm_level").handler("其他", 0.0)["level"] == "提示"


def test_grade_defect():
    assert get_tool("grade_defect").handler("严重发热，随时可能损坏")["level"] == "危急"


def test_diagnose_finding():
    r = get_tool("diagnose").handler("开关柜", {"局放": 150, "温度": 90})
    assert r["degraded"] is False and r["fault_type"] is not None


def test_diagnose_degrade():
    r = get_tool("diagnose").handler("开关柜", {"局放": None})
    assert r["degraded"] is True


def test_workorder_draft():
    r = get_tool("create_workorder_draft").handler("危急", "变压器油温严重超标", device_id="DEV000001")
    assert r["draft"]["level"] == "危急"
    assert r["draft"]["status"] == "草稿"
    assert r["draft"]["deadline"] is not None


def test_deadline():
    assert get_tool("deadline_for").handler("危急")["hours"] == 24
