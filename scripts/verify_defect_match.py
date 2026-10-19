"""验证缺陷库嵌入匹配：跑几个案例，看嵌入相似度匹配的效果。

用法：python scripts/verify_defect_match.py
首次运行会嵌入 5964 条记录建缓存（几分钟），之后秒回。
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.engine.rule_engine import RuleEngine

CASES = [
    ("无法储能", "断路器"),
    ("无法储能", "柱上"),
    ("绝缘电阻不合格", None),
    ("套管闪络", None),
    ("水泥杆杆身有纵向裂纹", None),
]


def main() -> None:
    e = RuleEngine()
    print("首次可能花几分钟建嵌入缓存，稍等...\n")
    for desc, dt in CASES:
        r = e.grade_defect(desc, device_type=dt)
        tag = dt or "无设备"
        print(f"  [{tag}] {desc} -> {r['level']} (degraded={r['degraded']})")


if __name__ == "__main__":
    main()
