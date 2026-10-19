# -*- coding: utf-8 -*-
"""
多模型缺陷分级审核结果对比脚本

用法:
    python compare_reviews.py a.csv b.csv [c.csv ...]

输入 CSV 格式 (UTF-8 带 BOM, 列顺序固定):
    等级,序号,src,desc,判定,纠正
    例如: 一般,60,泄漏电流指示值超标,漏电流表上的数比一开始低了...,✗,删除

每条记录用 "等级-序号" 作为唯一键 (如 一般-60)。
判定列只接受 ✓/✗ (其他值会被归为无效)。

输出:
    1) 两两一致率矩阵
    2) 逐条分歧清单 (哪些模型判了不同结果)
    3) 共识判 ✗ 的条目
    4) 各模型 ✓/✗ 统计
"""
import csv
import os
import sys
from itertools import combinations


def load(path):
    """读取一个模型的审核结果 CSV，返回 {key: (判定, 纠正)}"""
    d = {}
    with open(path, encoding="utf-8-sig", newline="") as f:
        reader = csv.reader(f)
        header = next(reader, None)  # 跳过表头
        for row in reader:
            if len(row) < 5:
                continue
            lvl, idx = row[0].strip(), row[1].strip()
            verdict = row[4].strip()
            corr = row[5].strip() if len(row) > 5 else ""
            if not lvl or not idx:
                continue
            d[f"{lvl}-{idx}"] = (verdict, corr)
    return d


def model_name(path):
    base = os.path.basename(path)
    return os.path.splitext(base)[0]


def main():
    paths = sys.argv[1:]
    if len(paths) < 2:
        print(__doc__)
        print("错误: 至少需要 2 个 CSV 文件才能对比。")
        return

    models = {model_name(p): load(p) for p in paths}
    all_keys = set()
    for m in models.values():
        all_keys |= set(m.keys())
    keys = sorted(all_keys, key=lambda k: (k.split("-")[0], int(k.split("-")[1])))

    # ---- 1) 两两一致率 ----
    print("=== 1) 两两一致率 (仅比较判定列) ===")
    for a, b in combinations(models, 2):
        common = [k for k in keys if k in models[a] and k in models[b]]
        if not common:
            print(f"{a} vs {b}: 无共同条目")
            continue
        agree = sum(1 for k in common if models[a][k][0] == models[b][k][0])
        pct = agree / len(common) * 100
        print(f"{a} vs {b}: {agree}/{len(common)} = {pct:.1f}%")

    # ---- 2) 逐条分歧 ----
    print("\n=== 2) 分歧条目 (各模型判定不一致) ===")
    diff_count = 0
    for k in keys:
        vs = {m: (models[m][k][0] if k in models[m] else "缺失") for m in models}
        if len(set(vs.values())) > 1:
            diff_count += 1
            detail = " | ".join(f"{m}={v}" for m, v in vs.items())
            print(f"  {k}: {detail}")
    if diff_count == 0:
        print("  (无分歧，所有模型判定完全一致)")

    # ---- 3) 共识判 ✗ ----
    print("\n=== 3) 共识判 ✗ 的条目 (所有模型都认为失真) ===")
    any_x = False
    for k in keys:
        vs = [models[m][k][0] for m in models if k in models[m]]
        if vs and all(v == "✗" for v in vs):
            any_x = True
            print(f"  {k}")
    if not any_x:
        print("  (无)")

    # ---- 4) 各模型统计 ----
    print("\n=== 4) 各模型 ✓/✗ 统计 ===")
    for m in models:
        vals = [v[0] for v in models[m].values()]
        ok = sum(1 for v in vals if v == "✓")
        ng = sum(1 for v in vals if v == "✗")
        other = len(vals) - ok - ng
        extra = f", 无效={other}" if other else ""
        print(f"  {m}: 总{len(vals)} 条, ✓={ok}, ✗={ng}{extra}")


if __name__ == "__main__":
    main()
