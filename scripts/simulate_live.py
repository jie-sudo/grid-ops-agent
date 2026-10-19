"""实时数据模拟器：定时更新量测值、插入时序、越限产生告警，模拟设备实时运行。

用法（后台跑着，保持服务运行）：
    python scripts/simulate_live.py --interval 3

前端轮询 /devices/{id}/overview 即可看到实时变化。
"""
from __future__ import annotations

import argparse
import random
import sys
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.data import models
from app.data.database import get_write_session

# 量测类型 → (上限, 均值, 波动幅度)
MEASURE_SPECS = {
    "温度": (85.0, 60.0, 8.0),
    "电流": (500.0, 200.0, 40.0),
    "电压": (10.6, 10.0, 0.2),
    "局放": (100.0, 30.0, 12.0),
    "护层电流": (5.0, 1.0, 0.6),
    "油色谱": (100.0, 30.0, 12.0),
}

# 量测类型 → 告警类型
ALARM_TYPE_MAP = {
    "温度": "过温",
    "电流": "过流",
    "局放": "局放",
    "电压": "越限",
    "护层电流": "越限",
    "油色谱": "越限",
}


def tick(sample_ratio: float) -> int:
    """一轮更新：给量测加噪声、插入时序、越限产生告警。返回更新点数。"""
    now = datetime.now(timezone.utc)
    updated = 0
    with get_write_session() as s:
        points = s.query(models.MeasurePoint).all()
        random.shuffle(points)
        for p in points[: max(1, int(len(points) * sample_ratio))]:
            upper, mean, std = MEASURE_SPECS.get(p.measure_type, (100.0, 50.0, 10.0))
            # 随机游走：90% 小幅波动，10% 大幅波动（模拟异常）
            if random.random() < 0.1:
                new = max(0.0, mean + random.gauss(0, std * 2.0))
            else:
                new = max(0.0, (p.latest_value or mean) + random.gauss(0, std * 0.25))
            new = round(new, 3)
            p.latest_value = new
            quality = "越限" if new > upper else "正常"

            s.add(models.MeasureValue(
                value_id=f"MV{uuid.uuid4().hex[:16]}",
                point_id=p.point_id,
                ts=now,
                value=new,
                quality=quality,
            ))

            # 越限且概率触发 → 产生告警
            if new > upper and random.random() < 0.4:
                ratio = (new - upper) / upper if upper else 0.0
                level = "紧急" if ratio > 0.5 else ("重要" if ratio > 0.2 else "提示")
                s.add(models.Alarm(
                    alarm_id=f"AL{uuid.uuid4().hex[:12]}",
                    device_id=p.device_id,
                    alarm_type=ALARM_TYPE_MAP.get(p.measure_type, "越限"),
                    level=level,
                    trigger_time=now,
                    related_point=p.point_id,
                    status="活动",
                ))
            updated += 1
        s.commit()
    return updated


def main() -> None:
    parser = argparse.ArgumentParser(description="实时数据模拟器")
    parser.add_argument("--interval", type=int, default=3, help="更新间隔（秒）")
    parser.add_argument("--sample", type=float, default=1.0, help="每轮更新的量测点比例（0~1）")
    args = parser.parse_args()

    print(f"实时模拟器启动：每 {args.interval}s 更新 {args.sample:.0%} 量测点（Ctrl+C 停止）")
    while True:
        n = tick(args.sample)
        print(f"[{datetime.now().strftime('%H:%M:%S')}] 更新 {n} 个量测点")
        time.sleep(args.interval)


if __name__ == "__main__":
    main()
