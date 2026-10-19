"""缺陷库定级压测：对比 bigram vs 嵌入匹配。

从缺陷库采样 N 条，用记录自身的 defect+basis 做定级输入（开卷），
统计三种结果：命中（返回等级==正确）、降级（返回 None，安全交人工）、
误判（返回了等级但错了，最危险）。

用法：python scripts/eval_defect_grading.py --sample 500
首次跑会嵌入 5964 条建缓存（几分钟），之后快。
"""
from __future__ import annotations

import argparse
import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import yaml

from app.data.defect_lib import match_by_bigram
from app.data.defect_embeddings import match_by_embedding

RULES = Path(__file__).resolve().parents[1] / "rules"


def load() -> list[dict]:
    records = []
    for name in ("defect_library.yaml", "defect_library_1906.yaml"):
        p = RULES / name
        if p.exists():
            records += yaml.safe_load(p.read_text(encoding="utf-8")).get("defects", [])
    return records


def eval_match(match_fn, records, samples):
    hit = degrade = wrong = 0
    wrong_cases = []
    for r in samples:
        inp = " ".join(x for x in [r.get("defect", ""), r.get("basis", "")] if x).strip()
        level, _ = match_fn(inp, records)
        if level is None:
            degrade += 1
        elif level == r["level"]:
            hit += 1
        else:
            wrong += 1
            wrong_cases.append((inp[:40], r["level"], level))
    return hit, degrade, wrong, wrong_cases


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--sample", type=int, default=500)
    args = ap.parse_args()

    records = load()
    n = min(args.sample, len(records))
    rng = random.Random(42)
    samples = rng.sample(records, n)
    print(f"缺陷库 {len(records)} 条，采样 {n} 条\n")

    print("嵌入匹配（首次建缓存，稍等）...")
    h2, d2, w2, wc2 = eval_match(match_by_embedding, records, samples)
    print("bigram 匹配 ...")
    h1, d1, w1, wc1 = eval_match(match_by_bigram, records, samples)

    print(f"{'指标':<12}{'bigram':>10}{'嵌入':>10}")
    print("-" * 34)
    print(f"{'命中率':<12}{h1/n:>9.1%}{h2/n:>9.1%}")
    print(f"{'降级率':<12}{d1/n:>9.1%}{d2/n:>9.1%}")
    print(f"{'误判率':<12}{w1/n:>9.1%}{w2/n:>9.1%}")

    if wc2:
        print("\n嵌入误判样例（描述 | 正确等级 | 判成）：")
        for c in wc2[:5]:
            print(f"  {c[0]} | {c[1]} | {c[2]}")


if __name__ == "__main__":
    main()
