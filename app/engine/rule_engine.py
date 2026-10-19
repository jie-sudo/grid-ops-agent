"""规则引擎：确定性计算（分级 / 时限 / 等级映射 / 冲突裁决）。

对应 SDD 4.4、BR-001~006、FR-040/041。规则以 YAML 数据驱动，非代码硬编码，
便于电力专家审改 rules/*.yaml。
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from app.data.defect_lib import match_defect_library

RULES_DIR = Path(__file__).resolve().parents[2] / "rules"

# 缺陷等级严重程度排序（用于冲突裁决取最高）
_LEVEL_ORDER = ["一般", "严重", "危急"]


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
    def grade_defect(self, description: str, measurements: dict | None = None, device_type: str | None = None) -> dict:
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
        # 5. 仍未命中 → 降级人工复核，绝不默认"一般"（安全兜底）
        return {"level": None, "reasons": ["无法确定缺陷等级"], "degraded": True}

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
