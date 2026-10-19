"""M2 验收测试：缺陷分级 / 时限映射 / 等级映射 / 冲突裁决 / 诊断降级。"""
from app.engine.rule_engine import RuleEngine
from app.packs import get_pack

engine = RuleEngine()


def test_deadline_mapping():
    assert engine.deadline_for("危急")["hours"] == 24
    assert engine.deadline_for("严重")["days"] == 30
    assert engine.deadline_for("一般")["type"] == "plan"


def test_defect_grading():
    assert engine.grade_defect("轻微异常，暂不影响运行，可列入计划处理")["level"] == "一般"
    assert engine.grade_defect("温度明显偏高，存在隐患，需尽快安排处理")["level"] == "严重"
    assert engine.grade_defect("严重发热，随时可能损坏，须立即处理")["level"] == "危急"


def test_conflict_resolution():
    assert engine.resolve_conflict(["一般", "严重"]) == "严重"
    assert engine.resolve_conflict(["严重", "危急"]) == "危急"


def test_level_mapping():
    assert engine.map_alarm_to_defect("紧急") == "危急"
    assert engine.map_alarm_to_defect("重要") == "严重"
    assert engine.map_alarm_to_defect("提示") == "一般"
    assert engine.map_state_to_defect("正常") is None
    assert engine.map_state_to_defect("严重") == "危急"


def test_diagnosis_degradation():
    pack = get_pack("开关柜")
    r = pack.diagnose({"局放": None})
    assert r["degraded"] is True
    assert r["fault_type"] is None


def test_diagnosis_finding():
    pack = get_pack("开关柜")
    r = pack.diagnose({"局放": 150, "温度": 90})
    assert r["degraded"] is False
    assert r["fault_type"] is not None
    assert len(r["basis"]) >= 1


def test_diagnosis_normal():
    pack = get_pack("变压器")
    r = pack.diagnose({"温度": 60, "油色谱": 30, "护层电流": 1})
    assert r["degraded"] is False
    assert r["fault_type"] == "正常"
