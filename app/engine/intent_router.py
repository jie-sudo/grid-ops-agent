"""意图路由：规则优先 + LLM 兜底（FR-001，软先验不锁工具）。"""
from __future__ import annotations

from app.engine.llm import LLMClient, LLMError

INTENTS = ["问答", "状态查询", "告警分析", "缺陷分级", "故障诊断", "工单生成", "其他"]

# 规则层关键词（按优先级顺序，命中即返回）
RULES: list[tuple[str, list[str]]] = [
    ("工单生成", ["工单", "派单"]),
    ("告警分析", ["告警", "报警"]),
    ("缺陷分级", ["缺陷", "分级", "定级"]),
    ("故障诊断", ["诊断", "故障", "局放", "过热"]),
    ("状态查询", ["温度", "电流", "电压", "量测", "台账", "状态"]),
    ("问答", ["规程", "标准", "依据", "处置", "规定", "规范"]),
]

# 否定词：命中则规则层不硬匹配，交给 LLM 兜底
NEGATIONS = ("不要", "别", "不用", "不是", "难道", "不需要")


class IntentRouter:
    def __init__(self) -> None:
        self.llm = LLMClient()

    def route(self, text: str) -> tuple[str, float]:
        # 否定词 → 跳过规则层硬命中，交给 LLM 兜底理解语义（"不要出工单"不应命中"工单"）
        negated = any(n in text for n in NEGATIONS)
        if not negated:
            for intent, kws in RULES:
                if any(kw in text for kw in kws):
                    return intent, 0.9
        # LLM 兜底（含否定词时）
        try:
            out = self.llm.chat_json([
                {
                    "role": "system",
                    "content": f"你是意图分类器，把用户问题分为七类之一：{INTENTS}。"
                               f"只输出 JSON：{{\"intent\":\"...\",\"confidence\":0.x}}",
                },
                {"role": "user", "content": text},
            ])
            intent = out.get("intent")
            if intent in INTENTS:
                return intent, float(out.get("confidence", 0.5))
        except LLMError:
            pass
        return "其他", 0.5
