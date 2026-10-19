"""安全闸口：二次确认判定 / 降级识别 / 输出来源校验 / 幻觉溯源（SDD 4.1.4）。"""
from __future__ import annotations

import json
import re


class Guards:
    def is_confirm_needed(self, result: dict) -> bool:
        """结果含工单草稿 → 需二次确认（FR-004/061）。"""
        return isinstance(result, dict) and result.get("draft") is not None

    def is_degraded(self, result: dict) -> bool:
        """结果标记降级 → 结论应提示"建议人工复核"（FR-052）。"""
        return isinstance(result, dict) and result.get("degraded") is True

    def ensure_sources(self, answer: str, sources: list | None, used_knowledge: bool) -> tuple[bool, str]:
        """输出校验：用到知识/诊断工具时，结论必须附来源（FR-011）。"""
        if used_knowledge and not sources:
            return False, "结论缺少来源"
        return True, ""

    def check_fabrication(self, answer: str, tool_results: list, user_text: str | None = None) -> list[str]:
        """幻觉溯源：答案里的数值若无法追溯到工具返回/用户输入，标记为可疑（提示人工核实，不拦截）。"""
        if not tool_results:
            return []
        known: set[str] = set()
        if user_text:
            known.update(re.findall(r"\b\d+(?:\.\d+)?\b", user_text))
        for r in tool_results:
            known.update(re.findall(r"\b\d+(?:\.\d+)?\b", json.dumps(r, ensure_ascii=False, default=str)))
        suspicious = [
            n for n in re.findall(r"\b\d+(?:\.\d+)?\b", answer)
            if n not in known and float(n) > 1
        ]
        return suspicious[:5]
