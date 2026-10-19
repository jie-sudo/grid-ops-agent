"""数据源适配器框架单测（纯逻辑，不碰 DB）。"""
from app.data.source import DataSource, MockDataSource, get_datasource


def test_get_datasource_default_mock():
    assert isinstance(get_datasource(), MockDataSource)


def test_datasource_singleton():
    assert get_datasource() is get_datasource()


def test_datasource_registry_has_mock():
    from app.data.source import _REGISTRY

    assert "mock" in _REGISTRY
    assert _REGISTRY["mock"] is MockDataSource


def test_mock_datasource_has_interface_methods():
    ds = MockDataSource()
    for m in ("get_device", "list_devices", "query_measurements", "get_latest_value", "query_alarms"):
        assert callable(getattr(ds, m))
