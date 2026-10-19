"""数据源适配器框架：把「设备/量测/告警数据从哪来」抽象出来。

当前只有 Mock 实现（查 PostgreSQL 的模拟数据）；接入真实数据（SCADA / 在线监测 / PMS）时，
实现一个新的 DataSource 子类、在 get_datasource() 里按配置返回即可，业务层零改动。

用法：config 里设 `DATA_SOURCE=mock`（默认）或 `DATA_SOURCE=<新适配器名>`。
"""
from __future__ import annotations

from abc import ABC, abstractmethod

from app.config import get_settings
from app.data import repository


class DataSource(ABC):
    """数据源抽象接口：业务层只依赖这个接口，不关心数据从哪来。"""

    @abstractmethod
    def get_device(self, device_id: str) -> dict | None:
        ...

    @abstractmethod
    def list_devices(self, keyword: str | None = None, limit: int = 50) -> list[dict]:
        ...

    @abstractmethod
    def query_measurements(self, device_id: str, measure_type: str | None = None, hours: int = 24) -> list[dict]:
        ...

    @abstractmethod
    def get_latest_value(self, device_id: str, measure_type: str) -> float | None:
        ...

    @abstractmethod
    def query_alarms(self, device_id: str | None = None, hours: int = 24) -> list[dict]:
        ...


class MockDataSource(DataSource):
    """模拟数据源：查 PostgreSQL 里的 mock 数据（现状）。"""

    def get_device(self, device_id: str) -> dict | None:
        return repository.get_device(device_id)

    def list_devices(self, keyword: str | None = None, limit: int = 50) -> list[dict]:
        return repository.list_devices(keyword, limit)

    def query_measurements(self, device_id: str, measure_type: str | None = None, hours: int = 24) -> list[dict]:
        return repository.query_measurements(device_id, measure_type, hours)

    def get_latest_value(self, device_id: str, measure_type: str) -> float | None:
        return repository.get_latest_value(device_id, measure_type)

    def query_alarms(self, device_id: str | None = None, hours: int = 24) -> list[dict]:
        return repository.query_alarms(device_id, hours)


# 注册表：数据源名 -> 类。接入真实数据时在这里加一个适配器即可。
_REGISTRY: dict[str, type[DataSource]] = {
    "mock": MockDataSource,
}

_datasource: DataSource | None = None


def get_datasource() -> DataSource:
    """按配置返回数据源单例（默认 mock）。"""
    global _datasource
    if _datasource is None:
        name = get_settings().data_source
        cls = _REGISTRY.get(name, MockDataSource)
        _datasource = cls()
    return _datasource
