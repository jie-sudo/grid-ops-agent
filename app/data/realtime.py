"""实时量测数据源抽象（对接 PMS/监测系统的关键接口）。

设计目标：业务代码只依赖 RealtimeSource 接口。
- 现在用 SimulatedSource（模拟器，由 scripts/simulate_live.py 持续更新数据）。
- 接真实 PMS/监测系统时，实现 PMSSource 即可，业务代码（overview / query_state）零改动。

切换方式：改 get_source() 返回 PMSSource 实例。
"""
from __future__ import annotations

from abc import ABC, abstractmethod

from app.data import models
from app.data.database import get_read_session


class RealtimeSource(ABC):
    """实时量测数据源接口。"""

    @abstractmethod
    def get_latest(self, device_id: str) -> dict[str, float | None]:
        """获取某设备的最新量测值，返回 {量测类型: 数值}。

        量测类型为内部标准枚举：温度/电流/电压/局放/护层电流/油色谱。
        """


class SimulatedSource(RealtimeSource):
    """模拟数据源：读 measure_point.latest_value（由 simulate_live.py 持续更新）。"""

    def get_latest(self, device_id: str) -> dict[str, float | None]:
        with get_read_session() as s:
            rows = s.query(models.MeasurePoint).filter_by(device_id=device_id).all()
        return {r.measure_type: r.latest_value for r in rows}


class PMSSource(RealtimeSource):
    """PMS / 监测系统数据源（预留）。

    接真实数据时实现 get_latest：
    1. 调用 PMS API 获取设备最新量测（按设备编号查询）。
    2. 把 PMS 的量测项映射到内部标准枚举：

       PMS 项        → 内部 measure_type
       ─────────────────────────────────
       油温/绕组温度  → 温度
       负荷电流       → 电流
       运行电压       → 电压
       局放量         → 局放
       护层电流       → 护层电流
       油色谱(H2等)   → 油色谱

    3. 返回 {内部类型: 数值}，无数据的类型返回 None。
    """

    def __init__(self, base_url: str, api_key: str | None = None) -> None:
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key

    def get_latest(self, device_id: str) -> dict[str, float | None]:
        # TODO: 调 PMS API（GET {base_url}/devices/{device_id}/latest）
        # 按上面映射表转换后返回
        raise NotImplementedError("PMS 数据源待接入")


_source: RealtimeSource | None = None


def get_source() -> RealtimeSource:
    """当前实时数据源。接真实 PMS 时改为：return PMSSource(base_url=..., api_key=...)"""
    global _source
    if _source is None:
        _source = SimulatedSource()
    return _source
