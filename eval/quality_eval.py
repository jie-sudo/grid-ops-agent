"""缺陷分级 + 意图分类的量化评估（规则层，不需 LLM/DB）。

用法：python eval/quality_eval.py
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.engine.intent_router import IntentRouter
from app.engine.rule_engine import RuleEngine

# 缺陷分级样本（描述 → 期望等级）。"人工复核"= 规则层无法确定，应降级而非硬判。
DEFECT_SAMPLES = [
    # 三级定义标准措辞
    ("轻微异常，暂不影响运行，可列入计划处理", "一般"),
    ("设备本身及周围环境出现不正常情况，一般不威胁设备安全运行", "一般"),
    ("情况较轻、影响较小，可列计划消除", "一般"),
    ("温度明显偏高，存在隐患，需尽快安排处理", "严重"),
    ("设备处于异常状态，可能发展为事故，但可继续运行", "严重"),
    ("局放超标，须加强监视", "严重"),
    ("严重发热，随时可能损坏，须立即处理", "危急"),
    ("严重威胁设备安全运行，不及时处理随时可能导致事故", "危急"),
    ("击穿放电，立即停运", "危急"),
    ("烧损冒烟，随时可能起火", "危急"),
    # 真实设备缺陷描述
    ("开关柜触头温升超标", "严重"),
    ("变压器油位异常降低", "严重"),
    ("电缆护层绝缘受损", "严重"),
    ("断路器拒分拒合", "危急"),
    ("GIS 气室压力异常", "严重"),
    ("避雷器泄漏电流增大", "严重"),
    ("绝缘子破损", "严重"),
    ("保护装置误动", "危急"),
    ("电容器渗油", "严重"),
    ("SF6 气体湿度超标", "严重"),
    # 无法确定 → 应人工复核
    ("导线弧垂过大", "人工复核"),
    ("杆塔基础沉降", "严重"),
    ("二次回路接线松动", "人工复核"),
    ("蓄电池电压偏低", "人工复核"),
]

INTENT_SAMPLES = [
    ("帮我出个工单", "工单生成"),
    ("生成一个工单", "工单生成"),
    ("派个工单", "工单生成"),
    ("这个缺陷是什么等级", "缺陷分级"),
    ("缺陷定级", "缺陷分级"),
    ("缺陷定级一下", "缺陷分级"),
    ("这个告警是什么等级", "告警分析"),
    ("告警分析一下", "告警分析"),
    ("有什么告警", "告警分析"),
    ("这台变压器是什么故障", "故障诊断"),
    ("诊断一下局放异常", "故障诊断"),
    ("这台开关柜局放怎么样", "故障诊断"),
    ("这台变压器温度多少", "状态查询"),
    ("查询设备台账", "状态查询"),
    ("帮我看下台账", "状态查询"),
    ("测一下温度", "状态查询"),
    ("变压器缺陷按规程怎么处置", "问答"),
    ("查阅相关标准", "问答"),
    ("按规程处理", "问答"),
]


def eval_defect() -> dict:
    engine = RuleEngine()
    correct = 0
    detail = []
    for desc, want in DEFECT_SAMPLES:
        r = engine.grade_defect(desc)
        got = "人工复核" if r["degraded"] else r["level"]
        ok = got == want
        correct += ok
        detail.append(f"{'✓' if ok else '✗'} {desc[:24]} → {got} (期望 {want})")
    acc = correct / len(DEFECT_SAMPLES)
    print(f"缺陷分级准确率：{correct}/{len(DEFECT_SAMPLES)} = {acc:.1%}")
    for d in detail:
        print("  " + d)
    return {"correct": correct, "total": len(DEFECT_SAMPLES), "accuracy": acc}


def eval_intent() -> dict:
    router = IntentRouter()
    correct = 0
    detail = []
    for text, want in INTENT_SAMPLES:
        got = router.route(text)[0]
        ok = got == want
        correct += ok
        detail.append(f"{'✓' if ok else '✗'} {text} → {got} (期望 {want})")
    acc = correct / len(INTENT_SAMPLES)
    print(f"\n意图识别准确率（规则层）：{correct}/{len(INTENT_SAMPLES)} = {acc:.1%}")
    for d in detail:
        print("  " + d)
    return {"correct": correct, "total": len(INTENT_SAMPLES), "accuracy": acc}


if __name__ == "__main__":
    eval_defect()
    eval_intent()
