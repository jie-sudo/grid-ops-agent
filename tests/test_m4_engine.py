"""M4 验收：意图路由（规则层）+ 工具调度器 + 闸口（不需 LLM/DB/Redis）。"""
from app.engine.guards import Guards
from app.engine.intent_router import IntentRouter
from app.engine.tool_dispatcher import ToolDispatcher


def test_intent_router_rules():
    r = IntentRouter()
    assert r.route_rules("帮我出个工单")[0] == "工单生成"
    assert r.route_rules("这个缺陷是什么等级") is None  # 「缺陷」不再是关键词，交 LLM 兜底
    assert r.route_rules("这台变压器温度多少")[0] == "状态查询"


def test_dispatcher_execute():
    d = ToolDispatcher()
    assert d.execute("grade_defect", {"description": "严重发热，随时可能损坏"})["level"] == "危急"


def test_dispatcher_unknown_tool():
    d = ToolDispatcher()
    assert "error" in d.execute("nonexistent", {})


def test_dispatcher_param_coercion():
    d = ToolDispatcher()
    r = d.execute("alarm_level", {"alarm_type": "过温", "over_ratio": "0.6"})
    assert r["level"] == "紧急"  # 字符串 "0.6" 被强转 float


def test_dispatcher_missing_required():
    d = ToolDispatcher()
    assert "error" in d.execute("grade_defect", {})


def test_guards_confirm():
    g = Guards()
    assert g.is_confirm_needed({"draft": {"content": "x"}}) is True
    assert g.is_confirm_needed({"level": "一般"}) is False
    assert g.is_degraded({"degraded": True}) is True
