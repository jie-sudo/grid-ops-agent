"""数据接入适配器：CSV/JSON → 内部数据模型（对应 IF-001）。

预留 PMS/监测系统适配器接口，本期以 CSV/JSON + 模拟数据验证。
"""
from __future__ import annotations

import pandas as pd
from sqlalchemy import Engine

TABLE_COLUMNS: dict[str, list[str]] = {
    "device": ["device_id", "device_name", "device_type", "voltage_level", "station",
               "commission_date", "rated_params", "status"],
    "measure_point": ["point_id", "device_id", "measure_type", "unit",
                      "threshold_upper", "threshold_lower", "latest_value"],
    "measure_value": ["value_id", "point_id", "ts", "value", "quality"],
    "defect": ["defect_id", "device_id", "location", "description", "level",
               "discover_time", "deadline", "status", "source"],
    "alarm": ["alarm_id", "device_id", "alarm_type", "level", "trigger_time",
              "related_point", "status"],
}


class DataAdapter:
    """适配器基类：外部数据 → 内部表。"""

    def __init__(self, engine: Engine) -> None:
        self.engine = engine

    def load(self, table: str, df: pd.DataFrame) -> int:
        cols = TABLE_COLUMNS.get(table)
        if cols is None:
            raise ValueError(f"未知表：{table}")
        df = df[[c for c in cols if c in df.columns]]
        df.to_sql(table, self.engine, if_exists="append", index=False, method="multi", chunksize=10000)
        return len(df)


class CsvAdapter(DataAdapter):
    """CSV 接入。"""

    def load_csv(self, table: str, path: str) -> int:
        df = pd.read_csv(path)
        return self.load(table, df)


class JsonAdapter(DataAdapter):
    """JSON 接入（records 格式）。"""

    def load_json(self, table: str, path: str) -> int:
        df = pd.read_json(path, orient="records")
        return self.load(table, df)
