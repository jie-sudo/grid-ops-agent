"""意图路由：规则优先 + LLM few-shot 兜底（FR-001，软先验不锁工具）。

v2：七类并五类——「告警分析 / 故障诊断 / 缺陷分级」合并为「异常处置」（口语不可分，交给
ReAct 工具调度）。规则层只保留高精确动作词，其余走 LLM few-shot 兜底。
见 docs/意图识别边界重划方案.md。
"""
from __future__ import annotations

import logging

from app.engine.llm import LLMClient, LLMError

logger = logging.getLogger(__name__)

INTENTS = ["问答", "状态查询", "异常处置", "工单生成", "其他"]

# 规则层关键词（按优先级顺序，命中即返回）。只保留高精确词；「缺陷/告警/诊断/故障」等
# 宽泛词在闭卷口语下精确率为 0，已移除，交 LLM 兜底。
RULES: list[tuple[str, list[str]]] = [
    ("工单生成", ["工单", "派单", "开单"]),
    ("状态查询", ["温度", "电流", "电压", "量测", "台账", "多少度", "几伏"]),
    ("问答", ["规程", "依据", "规定", "标准", "规范"]),
]

# 否定词：命中则规则层不硬匹配，交给 LLM 兜底
NEGATIONS = ("不要", "别", "不用", "不是", "难道", "不需要")

INTENT_SYSTEM = (
    "你是电网运维意图分类器，把用户问题分为五类之一。\n"
    "各类定义（必须按定义判断，不要凭关键词字面）：\n"
    "- 问答：问通用的规程/标准/依据/周期，不指向某台具体设备此刻的异常。\n"
    "- 状态查询：问某台具体设备此刻的读数/状态（多少度/几伏/合着还是断着/啥情况）。\n"
    "- 异常处置：设备或事件出了异常，要分析原因、定级或处理（咋回事/啥原因/要紧不/算哪级）。\n"
    "- 工单生成：明确要安排人去处理（安排人/派个活/开单/下单/去处理掉）。\n"
    "- 其他：闲聊或与电网运维无关。\n"
    "只输出 JSON：{\"intent\":\"...\",\"confidence\":0.x}"
)

FEWSHOT: list[tuple[str, str]] = [
    ("变压器渗油的处理规程是什么", "问答"),
    ("断路器多久检修一次", "问答"),
    ("1号主变现在多少度", "状态查询"),
    ("母线电压现在多少", "状态查询"),
    ("1号主变漏油了，咋回事", "异常处置"),
    ("主变差动保护跳了，帮我瞅瞅", "异常处置"),
    ("这设备的毛病算哪一档", "异常处置"),
    ("帮我在系统里开个单，安排人去处理", "工单生成"),
    ("这个缺陷派个活，让人去修", "工单生成"),
    ("今天天气怎么样", "其他"),
]


class IntentRouter:
    def __init__(self) -> None:
        self.llm = LLMClient()
        self.llm_failures = 0

    def route_rules(self, text: str) -> tuple[str, float] | None:
        """规则层：命中返回 (intent, 0.9)；否定词或未命中返回 None（交 LLM 兜底）。

        单独拆出便于评测规则层覆盖率/精确率（见 scripts/eval_intent_closed.py）。
        """
        if any(n in text for n in NEGATIONS):
            return None
        for intent, kws in RULES:
            if any(kw in text for kw in kws):
                return intent, 0.9
        return None

    def route(self, text: str) -> tuple[str, float]:
        hit = self.route_rules(text)
        if hit is not None:
            return hit
        return self._llm_route(text)

    def _llm_route(self, text: str) -> tuple[str, float]:
        """LLM few-shot 兜底（含否定词、未命中规则时）。"""
        messages = [{"role": "system", "content": INTENT_SYSTEM}]
        for q, a in FEWSHOT:
            messages.append({"role": "user", "content": q})
            # few-shot 的 assistant 回复也用 JSON 格式，与 system 指令一致；
            # 否则模型会学着输出裸意图词，导致 chat_json 解析失败被静默降级为「其他」。
            messages.append({"role": "assistant", "content": f'{{"intent":"{a}","confidence":0.95}}'})
        messages.append({"role": "user", "content": text})
        try:
            out = self.llm.chat_json(messages)
            intent = out.get("intent")
            if intent in INTENTS:
                return intent, float(out.get("confidence", 0.5))
        except LLMError:
            self.llm_failures += 1
            logger.warning("意图 LLM 兜底失败，降级为「其他」（累计 %d 次）", self.llm_failures)
        return "其他", 0.5
