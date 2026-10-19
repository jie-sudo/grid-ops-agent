"""故障诊断能力（FR-050~052）：调技能包确定性规则。"""
from __future__ import annotations

from app.packs import get_pack


def diagnose(device_type: str, measurements: dict[str, float | None]) -> dict:
    pack = get_pack(device_type)
    if pack is None:
        return {
            "fault_type": None,
            "confidence": 0.0,
            "basis": [],
            "degraded": True,
            "reason": f"设备类型[{device_type}]无技能包，建议人工复核",
        }
    return pack.diagnose(measurements)
