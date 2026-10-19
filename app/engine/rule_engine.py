"""规则引擎：确定性计算（分级 / 时限 / 等级映射 / 冲突裁决）。

对应 SDD 4.4、BR-001~006、FR-040/041。规则以 YAML 数据驱动，非代码硬编码，
便于电力专家审改 rules/*.yaml。
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from app.data.defect_lib import match_defect_library, recall_topk

RULES_DIR = Path(__file__).resolve().parents[2] / "rules"

# 缺陷等级严重程度排序（用于冲突裁决取最高）
_LEVEL_ORDER = ["一般", "严重", "危急"]

# 缺陷三级定义（供 LLM 定级兜底时作为分级依据注入 prompt）
_DEFECT_LEVEL_DEF = (
    "缺陷三级定义（Q/GDW 745）：\n"
    "- 一般缺陷：不威胁设备安全运行或影响较小，可列入年/季检修计划消除。\n"
    "- 严重缺陷：威胁设备安全运行，但尚能坚持运行一段时间，需尽快（30 天内）消除。\n"
    "- 危急缺陷：随时可能造成事故，必须立即（24 小时内）处理。\n"
)


def _load(name: str) -> dict[str, Any]:
    with open(RULES_DIR / name, encoding="utf-8") as f:
        return yaml.safe_load(f)


class RuleEngine:
    def __init__(self, rules_dir: Path | None = None) -> None:
        self.rules_dir = rules_dir or RULES_DIR
        self.level_mapping: dict = _load("level_mapping.yaml")
        self.defect_rules: dict = _load("defect_level.yaml")
        self.defect_library = {"defects": []}
        # 合并两个缺陷库：配电网(745) + 输变电(1906)
        for name in ("defect_library.yaml", "defect_library_1906.yaml"):
            try:
                self.defect_library["defects"] += _load(name).get("defects", [])
            except FileNotFoundError:
                pass

    # ---- 缺陷分级（FR-040）----
    def grade_defect(self, description: str, measurements: dict | None = None, device_type: str | None = None, use_llm: bool = True) -> dict:
        text = description or ""
        keywords: dict = self.defect_rules.get("keywords", {})

        def hit(level: str) -> str | None:
            return next((k for k in keywords.get(level, []) if k and k in text), None)

        # 否定/已消除语义 → 抑制正向判定（不算严重 / 严重发热但已消除 等）
        negated = any(w in text for w in ("不算", "不是", "不用", "不要", "已消除", "已处理", "已恢复", "暂不", "尚未"))

        # 1. 危急优先
        if m := hit("危急"):
            if negated:
                return {"level": None, "reasons": [f"命中危急词[{m}]但含否定/已消除语义"], "degraded": True}
            return {"level": "危急", "reasons": [f"命中关键词[{m}]"], "degraded": False}
        # 2. 轻度修饰词 → 一般
        if m := hit("一般"):
            return {"level": "一般", "reasons": [f"命中轻度词[{m}]"], "degraded": False}
        # 3. 严重
        if m := hit("严重"):
            if negated:
                return {"level": None, "reasons": [f"命中严重词[{m}]但含否定/已消除语义"], "degraded": True}
            return {"level": "严重", "reasons": [f"命中关键词[{m}]"], "degraded": False}
        # 4. 关键词未命中 → 缺陷库匹配兜底（安全：仅单一等级命中才定级，绝不默认一般）
        level, rec = match_defect_library(text, self.defect_library.get("defects", []), device_type=device_type)
        if level:
            where = rec.get("part") or rec.get("component") or ""
            return {
                "level": level,
                "reasons": [f"缺陷库匹配[{where}]：{rec.get('defect', '')[:50]}"],
                "degraded": False,
            }
        # 5. LLM 定级兜底（放宽 C1：确定性降级时，检索增强 LLM 定级，带证据溯源）
        if use_llm:
            lv, evidence = self._llm_grade(text, device_type)
            if lv:
                return {
                    "level": lv,
                    "reasons": [f"LLM 定级：匹配缺陷库条目[{evidence}]"],
                    "degraded": False,
                    "source": "llm",
                }
        # 6. 仍未命中 → 降级人工复核，绝不默认"一般"（安全兜底）
        return {"level": None, "reasons": ["无法确定缺陷等级"], "degraded": True}

    def _llm_grade(self, description: str, device_type: str | None = None):
        """确定性降级时的检索增强 LLM 定级（闭卷口语下命中率 ~96%，误判 ~3%）。

        做法：bigram 召回 top-k 条相似缺陷库记录（含等级 + 分类依据），让 LLM
        「从中选最匹配的一条、照它的等级输出」，而非自由判断（避免常识抢答把「一般」高估）。
        LLM 失败/无法判断 → 返回 (None, None)，由调用方降级人工复核，绝不编造。
        """
        from app.engine.llm import LLMClient, LLMError

        top = recall_topk(description, self.defect_library.get("defects", []), k=10, device_type=device_type)
        seen: set[tuple[str, str]] = set()
        entries: list[tuple[str, str]] = []  # (level, label)
        for score, rec in top:
            if score <= 0:
                continue
            d = (rec.get("defect") or "").strip()
            basis = (rec.get("basis") or "").strip()
            key = (d, basis)
            if not d or key in seen:
                continue
            seen.add(key)
            label = d + (f"（依据：{basis}）" if basis else "")
            entries.append((rec.get("level"), label))
        if not entries:
            return None, None

        refs = "\n".join(f"- [{lv}] {label}" for lv, label in entries)
        prompt = (
            "你是电网设备缺陷分级专家。你的任务是：从下面的「缺陷库相似条目」里，找出和目标缺陷描述"
            "最匹配的一条（描述的是同一缺陷现象、同一严重程度），直接输出那一条的等级。\n\n"
            "规则：\n"
            "1. 只做匹配，不要用自己的常识判断缺陷严重程度。即使某条库条目的等级和你的直觉不符，也照那条的等级输出。\n"
            "2. 注意目标描述里的程度词：「有点/轻微/略有」对应轻微的条目；「严重/厉害/穿/裂」对应严重的条目。\n"
            "3. 不要折中、不要猜。若确实找不到匹配的条目，level 填「无法判断」。\n\n"
            + _DEFECT_LEVEL_DEF
            + "\n缺陷库相似条目（按相似度排序）：\n"
            + refs
            + "\n\n目标缺陷描述：" + description + "\n"
            '\n只输出 JSON：{"level": "一般/严重/危急/无法判断", "match": "你匹配的那条条目的原文（不含前面的[等级]前缀）"}。\n'
        )
        try:
            client = LLMClient()
            raw = client.chat([{"role": "user", "content": prompt}], temperature=0.0).strip()
            if raw.startswith("```"):
                raw = raw.strip("`")
                if raw.lower().startswith("json"):
                    raw = raw[4:]
                raw = raw.strip()
            import json as _json

            out = _json.loads(raw)
            lv = out.get("level")
            match = out.get("match")
        except (LLMError, ValueError, AttributeError):
            return None, None

        if lv in ("一般", "严重", "危急"):
            evidence = match or entries[0][1]
            return lv, evidence
        return None, None

    # ---- 消缺时限（FR-041 / BR-005）----
    def deadline_for(self, level: str) -> dict:
        return dict(self.level_mapping.get("level_to_deadline", {}).get(level, {}))

    # ---- 等级映射（BR-002 / BR-003）----
    def map_alarm_to_defect(self, alarm_level: str) -> str:
        return self.level_mapping.get("alarm_to_defect", {}).get(alarm_level, "一般")

    def map_state_to_defect(self, state: str) -> str | None:
        return self.level_mapping.get("state_to_defect", {}).get(state)

    # ---- 冲突裁决（BR-006）：取最高等级 ----
    def resolve_conflict(self, levels: list[str]) -> str:
        return max(levels, key=lambda x: _LEVEL_ORDER.index(x)) if levels else "一般"


_engine: RuleEngine | None = None


def get_engine() -> RuleEngine:
    global _engine
    if _engine is None:
        _engine = RuleEngine()
    return _engine
