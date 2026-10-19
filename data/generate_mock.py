"""模拟数据生成脚本（M1）。

用法（在 grid-ops-agent 目录下）：
    python data/generate_mock.py --scale demo   # 快速演示：200 设备 / 2 万量测 / 1 万告警
    python data/generate_mock.py --scale full   # 验收规模：1000 设备 / 100 万量测 / 10 万告警

生成前会先建表（init_db），再批量写入。
"""
from __future__ import annotations

import argparse
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

# 保证从仓库根目录运行时能 import app 包（不依赖 pip install -e）
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import numpy as np
from sqlalchemy.orm import Session

from app.config import get_settings
from app.data.database import get_engine, init_db, init_roles
from app.data import models

DEVICE_TYPES = ["变压器", "开关柜", "电缆", "线路", "断路器"]
VOLTAGE_LEVELS = ["10kV", "35kV", "110kV", "220kV"]
STATIONS = ["城东站", "城西站", "高新站", "工业园站", "开发区站", "滨江站"]
DEVICE_STATUS = ["运行", "运行", "运行", "停运", "检修", "备用"]

# 量测类型 → (单位, 上限, 下限, 均值, 标准差)
MEASURE_SPECS: dict[str, tuple[str, float, float, float, float]] = {
    "温度": ("℃", 85.0, -40.0, 60.0, 15.0),
    "电流": ("A", 500.0, 0.0, 200.0, 80.0),
    "电压": ("kV", 10.6, 9.4, 10.0, 0.2),
    "局放": ("pC", 100.0, 0.0, 30.0, 20.0),
    "护层电流": ("A", 5.0, 0.0, 1.0, 1.0),
    "油色谱": ("μL/L", 100.0, 0.0, 30.0, 20.0),
}
MEASURE_TYPES = list(MEASURE_SPECS)

ALARM_TYPES = ["过温", "过流", "局放", "越限", "其他"]
ALARM_LEVELS = ["提示", "重要", "紧急"]
ALARM_LEVEL_P = [0.70, 0.25, 0.05]

DEFECT_LEVELS = ["一般", "严重", "危急"]
DEFECT_LEVEL_P = [0.70, 0.25, 0.05]
DEFECT_SOURCES = ["巡检", "告警", "诊断", "试验"]
DEFECT_LOCATIONS = ["本体", "套管", "触头", "接头", "绕组", "绝缘子", "电缆终端"]


def _now() -> datetime:
    return datetime.now(timezone.utc)


class _Inserter:
    """分块批量插入，控制内存占用（bulk_insert_mappings 不应用 Python 端默认值，故各字段须显式提供）。"""

    def __init__(self, session: Session, model, chunk: int = 20000) -> None:
        self.session = session
        self.model = model
        self.chunk = chunk
        self.buf: list[dict] = []

    def add(self, row: dict) -> None:
        self.buf.append(row)
        if len(self.buf) >= self.chunk:
            self._flush()

    def _flush(self) -> None:
        if self.buf:
            self.session.bulk_insert_mappings(self.model, self.buf)
            self.session.commit()
            self.buf.clear()

    def finish(self) -> None:
        self._flush()


def gen_devices(rng: np.random.Generator, n: int, now: datetime) -> list[dict]:
    rows = []
    for i in range(1, n + 1):
        dtype = DEVICE_TYPES[i % len(DEVICE_TYPES)]
        station = STATIONS[i % len(STATIONS)]
        rows.append({
            "device_id": f"DEV{i:06d}",
            "device_name": f"{station}{dtype}{i:04d}",
            "device_type": dtype,
            "voltage_level": VOLTAGE_LEVELS[i % len(VOLTAGE_LEVELS)],
            "station": station,
            "commission_date": now - timedelta(days=int(rng.integers(365, 3650))),
            "rated_params": {"额定容量": round(float(rng.uniform(50, 500)), 1)},
            "status": DEVICE_STATUS[i % len(DEVICE_STATUS)],
            "created_at": now,
            "updated_at": now,
        })
    return rows


def gen_points(rng: np.random.Generator, devices: list[dict], ppd: int, now: datetime) -> list[dict]:
    rows = []
    for d in devices:
        for k in range(ppd):
            mtype = MEASURE_TYPES[(len(rows)) % len(MEASURE_TYPES)]
            unit, upper, lower, mean, _std = MEASURE_SPECS[mtype]
            rows.append({
                "point_id": f"PT{len(rows) + 1:08d}",
                "device_id": d["device_id"],
                "measure_type": mtype,
                "unit": unit,
                "threshold_upper": upper,
                "threshold_lower": lower,
                "latest_value": round(float(mean + rng.normal(0, 5)), 3),
                "updated_at": now,
            })
    return rows


def gen_values(rng: np.random.Generator, points: list[dict], total: int, now: datetime, ins: _Inserter) -> int:
    per_point = max(1, total // len(points))
    count = 0
    for p in points:
        unit, upper, lower, mean, std = MEASURE_SPECS[p["measure_type"]]
        for k in range(per_point):
            # 少量越限 / 缺失 / 无效
            roll = rng.random()
            if roll < 0.01:
                value, quality = None, "缺失"
            elif roll < 0.02:
                value, quality = None, "无效"
            elif roll < 0.06:
                value = round(float(mean + rng.normal(0, std) * 1.8 + (upper - mean)), 3)
                quality = "越限" if value > upper else "正常"
            else:
                value = round(float(mean + rng.normal(0, std)), 3)
                quality = "越限" if value > upper else "正常"
            count += 1
            ins.add({
                "value_id": f"MV{count:012d}",
                "point_id": p["point_id"],
                "ts": now - timedelta(minutes=15 * k),
                "value": value,
                "quality": quality,
            })
    return count


def gen_alarms(rng: np.random.Generator, points: list[dict], n: int, now: datetime) -> list[dict]:
    point_by_device: dict[str, list[dict]] = {}
    for p in points:
        point_by_device.setdefault(p["device_id"], []).append(p)

    rows = []
    for i in range(1, n + 1):
        device_id = points[i % len(points)]["device_id"]
        level = rng.choice(ALARM_LEVELS, p=ALARM_LEVEL_P)
        p = point_by_device[device_id][i % len(point_by_device[device_id])]
        rows.append({
            "alarm_id": f"AL{i:08d}",
            "device_id": device_id,
            "alarm_type": ALARM_TYPES[i % len(ALARM_TYPES)],
            "level": level,
            "trigger_time": now - timedelta(seconds=int(rng.integers(60, 86400 * 7))),
            "related_point": p["point_id"],
            "status": "活动",
        })
    return rows


def gen_defects(rng: np.random.Generator, devices: list[dict], n: int, now: datetime) -> list[dict]:
    desc = {
        "一般": "轻微异常，暂不影响运行，可列入计划处理",
        "严重": "温度/局放明显偏高，存在隐患，需尽快安排处理",
        "危急": "严重发热/局放超标，随时可能损坏，须立即处理",
    }
    rows = []
    for i in range(1, n + 1):
        level = rng.choice(DEFECT_LEVELS, p=DEFECT_LEVEL_P)
        device = devices[i % len(devices)]
        rows.append({
            "defect_id": f"DF{i:08d}",
            "device_id": device["device_id"],
            "location": DEFECT_LOCATIONS[i % len(DEFECT_LOCATIONS)],
            "description": f"{device['device_type']}{DEFECT_LOCATIONS[i % len(DEFECT_LOCATIONS)]}{desc[level]}",
            "level": level,
            "discover_time": now - timedelta(days=int(rng.integers(1, 90))),
            "deadline": None,  # 分级后计算，创建时为空
            "status": "待处理",
            "source": DEFECT_SOURCES[i % len(DEFECT_SOURCES)],
        })
    return rows


def gen_knowledge_docs(now: datetime) -> list[dict]:
    samples = [
        ("变压器油温异常处置卡", "处置卡", "变压器", "油温超过 85℃ 时应降负荷运行，加强监视；超过 95℃ 立即停运检查。"),
        ("开关柜局放超标处置规程", "规程", "开关柜", "局放量超过 100pC 视为异常，应停电检查绝缘子与触头。"),
        ("电缆护层电流异常处理", "处置卡", "电缆", "护层电流超过 5A 时应检查接地与护层绝缘。"),
        ("配网设备状态评价标准", "标准", "通用", "状态四态：正常/注意/异常/严重；综合量测与缺陷判定。"),
        ("缺陷分级标准", "标准", "通用", "缺陷三级：一般/严重/危急；危急 24h 内消缺，严重 30 天内。"),
    ]
    rows = []
    for i, (title, dtype, domain, content) in enumerate(samples, 1):
        rows.append({
            "doc_id": f"KD{i:08d}",
            "title": title,
            "doc_type": dtype,
            "device_domain": domain,
            "content": content,
            "source": f"Q/GDW-{i:03d}",
            "tags": [domain, dtype],
            "vector_id": None,
        })
    return rows


def main() -> None:
    parser = argparse.ArgumentParser(description="生成模拟数据")
    parser.add_argument("--scale", choices=["demo", "full"], default="demo")
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()

    if args.scale == "full":
        n_devices, n_values, n_alarms, n_defects, ppd = 1000, 1_000_000, 100_000, 200, 8
    else:
        n_devices, n_values, n_alarms, n_defects, ppd = 200, 20_000, 10_000, 100, 5

    rng = np.random.default_rng(args.seed)
    now = _now()
    engine = get_engine()
    init_db(engine)
    init_roles(engine)
    session = Session(engine)

    t0 = datetime.now()

    def _bulk_insert(model, rows):
        ins = _Inserter(session, model)
        for r in rows:
            ins.add(r)
        ins.finish()

    # 1. 设备
    print(f"[1/5] 生成设备 {n_devices} 台 ...")
    devices = gen_devices(rng, n_devices, now)
    _bulk_insert(models.Device, devices)

    # 2. 量测点（measure_value 外键依赖）
    print(f"[2/5] 生成量测点 {len(devices) * ppd} 个 ...")
    points = gen_points(rng, devices, ppd, now)
    _bulk_insert(models.MeasurePoint, points)

    # 3. 量测时序（须在量测点之后）
    print(f"[3/5] 生成量测时序 {n_values} 条 ...")
    ins = _Inserter(session, models.MeasureValue)
    value_count = gen_values(rng, points, n_values, now, ins)
    ins.finish()

    # 4. 告警
    print(f"[4/5] 生成告警 {n_alarms} 条 ...")
    alarms = gen_alarms(rng, points, n_alarms, now)
    _bulk_insert(models.Alarm, alarms)

    # 5. 缺陷 + 知识文档
    print(f"[5/5] 生成缺陷 {n_defects} 条 + 样例知识文档 ...")
    defects = gen_defects(rng, devices, n_defects, now)
    docs = gen_knowledge_docs(now)
    _bulk_insert(models.Defect, defects)
    _bulk_insert(models.KnowledgeDoc, docs)

    session.close()
    print(f"完成：设备 {len(devices)}、量测点 {len(points)}、量测时序 {value_count}、告警 {len(alarms)}、缺陷 {len(defects)}、知识 {len(docs)}，耗时 {datetime.now() - t0}")


if __name__ == "__main__":
    main()
