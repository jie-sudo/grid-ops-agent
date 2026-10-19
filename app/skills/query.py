"""设备状态查询能力（FR-020/021/022）。"""
from __future__ import annotations

from app.data.source import get_datasource
from app.packs import get_pack


def query_device(device_id: str) -> dict:
    d = get_datasource().get_device(device_id)
    if d is None:
        return {"found": False, "message": f"设备 {device_id} 不存在，请核对编号"}
    return {"found": True, "device": d}


def query_measurements(device_id: str, measure_type: str | None = None, hours: int = 24) -> dict:
    values = get_datasource().query_measurements(device_id, measure_type, hours)
    return {"values": values, "count": len(values)}


def query_state(device_id: str) -> dict:
    """状态四态评价（FR-022，DL/T 1685 思路：量测 vs 阈值）。"""
    d = get_datasource().get_device(device_id)
    if d is None:
        return {"found": False, "message": f"设备 {device_id} 不存在"}
    pack = get_pack(d["device_type"])
    if pack is None:
        return {"found": True, "state": "正常", "basis": [f"设备类型[{d['device_type']}]无技能包"]}

    basis: list[str] = []
    max_ratio = -1.0
    for ch in pack.config.get("checks", []):
        mt = ch["measure_type"]
        val = get_datasource().get_latest_value(device_id, mt)
        if val is None:
            continue
        upper = ch.get("upper")
        ratio = (val - upper) / upper if upper else 0.0
        basis.append(f"{mt}={val}{ch.get('unit', '')}，上限={upper}{ch.get('unit', '')}，越限比例={ratio:.0%}")
        max_ratio = max(max_ratio, ratio)

    if max_ratio > 0.3:
        state = "严重"
    elif max_ratio > 0:
        state = "异常"
    elif max_ratio > -0.2:
        state = "注意"
    else:
        state = "正常"
    return {"found": True, "state": state, "basis": basis}
