"""技能包基类：按设备类型加载阈值表，执行确定性诊断（FR-050~052）。"""
from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

_PACKS_DIR = Path(__file__).resolve().parent
_RULES_DIR = _PACKS_DIR.parent.parent / "rules"


class BaseSkillPack:
    key: str = ""            # 技能包键（英文，对应 thresholds/{key}.yaml）
    device_type: str = ""    # 设备类型（中文，匹配 device.device_type）

    def __init__(self) -> None:
        self.config: dict[str, Any] = self._load_thresholds()

    def _load_thresholds(self) -> dict[str, Any]:
        path = _RULES_DIR / "thresholds" / f"{self.key}.yaml"
        with open(path, encoding="utf-8") as f:
            return yaml.safe_load(f)

    def diagnose(self, measurements: dict[str, float | None]) -> dict:
        """确定性诊断：阈值比对 → 故障类型 + 置信度 + 数据依据；数据不足降级（FR-052）。"""
        findings: list[dict] = []
        for ch in self.config.get("checks", []):
            mt = ch["measure_type"]
            value = measurements.get(mt)
            if value is None:
                # 数据不足 → 降级，不输出确定性诊断（FR-052）
                return {
                    "fault_type": None,
                    "confidence": 0.0,
                    "basis": [],
                    "degraded": True,
                    "reason": f"缺少量测[{mt}]，建议人工复核",
                }
            upper = ch.get("upper")
            if upper is not None and value > upper:
                ratio = (value - upper) / upper if upper else 0.0
                findings.append({
                    "fault_type": ch.get("fault_name", f"{mt}越限"),
                    "confidence": round(min(0.99, 0.6 + ratio * 0.3), 2),
                    "basis": f"{mt}={value}{ch.get('unit', '')}，上限={upper}{ch.get('unit', '')}",
                })

        if findings:
            top = max(findings, key=lambda x: x["confidence"])
            return {
                "fault_type": top["fault_type"],
                "confidence": top["confidence"],
                "basis": [f["basis"] for f in findings],
                "degraded": False,
                "reason": None,
            }
        return {
            "fault_type": "正常",
            "confidence": 0.9,
            "basis": ["各量测均在阈值内"],
            "degraded": False,
            "reason": None,
        }
