"""缺陷分级「闭卷完整链路」评测：验收口径（误判 = 安全红线）。

与 eval_defect_grading.py（开卷 bigram vs 嵌入对比）不同，本脚本走**完整定级链路**
`RuleEngine.grade_defect`（关键词规则 → 缺陷库匹配 → 降级人工复核），只给缺陷描述
（不带"分类依据"），用缺陷库 5964 条黄金标注做对拍，统计三种结果：

- 命中：返回等级 == 标注等级
- 降级：返回 None（安全交人工，不算错）
- 误判：返回了等级但错了（最危险，验收要求 = 0）

用法：
    python scripts/eval_defect_grading_closed.py                # 全量 5964
    python scripts/eval_defect_grading_closed.py --sample 500   # 采样
    python scripts/eval_defect_grading_closed.py --save         # 结果固化到 eval_run 表（评估看板）

口径说明：命中率是「自动化覆盖率」不是「准确率」；验收硬指标是误判率 ≈ 0。
提升命中率（当前带设备域约 31%）需「口语化输入归一化」，属后续迭代。
"""
from __future__ import annotations

import argparse
import random
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import yaml

from app.engine.rule_engine import get_engine

RULES = Path(__file__).resolve().parents[1] / "rules"


def load() -> list[dict]:
    records = []
    for name in ("defect_library.yaml", "defect_library_1906.yaml"):
        p = RULES / name
        if p.exists():
            records += yaml.safe_load(p.read_text(encoding="utf-8")).get("defects", [])
    return records


def evaluate(engine, records: list[dict], with_device: bool) -> tuple[int, int, int, list]:
    hit = degrade = wrong = 0
    wrong_cases = []
    for r in records:
        dt = r.get("device_type") if with_device else None
        res = engine.grade_defect(r["defect"], device_type=dt)
        lv = res["level"]
        if lv is None:
            degrade += 1
        elif lv == r["level"]:
            hit += 1
        else:
            wrong += 1
            wrong_cases.append((r["defect"][:30], r["level"], lv, r.get("device_type")))
    return hit, degrade, wrong, wrong_cases


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--sample", type=int, default=0, help="采样条数（0=全量）")
    ap.add_argument("--save", action="store_true", help="结果固化到 eval_run 表")
    args = ap.parse_args()

    records = load()
    n = len(records)
    if args.sample and args.sample < n:
        rng = random.Random(42)
        records = rng.sample(records, args.sample)
    n = len(records)

    engine = get_engine()
    print(f"缺陷库全量 {len(load())} 条，本次评测 {n} 条\n")

    results = {}
    for with_dev, label in ((True, "带设备域"), (False, "不带设备域")):
        t0 = time.time()
        hit, degrade, wrong, wc = evaluate(engine, records, with_dev)
        dt = time.time() - t0
        results[label] = {"hit": hit / n, "degrade": degrade / n, "wrong": wrong / n}
        print(f"[{label}] 命中 {hit} ({hit/n:.1%}) | 降级 {degrade} ({degrade/n:.1%}) | 误判 {wrong} ({wrong/n:.1%})  ({dt:.1f}s)")
        if wc:
            print("  误判样例：")
            for c in wc[:8]:
                print(f"    {c}")

    if args.save:
        from app.data import repository

        # 误判是硬指标：固化带设备域口径（更接近上线）
        m = results["带设备域"]
        repository.save_eval_run(
            suite="grading",
            metrics={
                "hit": round(m["hit"], 4),
                "degrade": round(m["degrade"], 4),
                "wrong": round(m["wrong"], 4),
                "n": n,
                "with_device": True,
            },
            sample_n=n,
            note="闭卷完整链路（grade_defect），缺陷库黄金标注对拍，误判=安全红线",
        )
        print(f"\n已固化到 eval_run：误判率 {m['wrong']:.1%}")


if __name__ == "__main__":
    main()
