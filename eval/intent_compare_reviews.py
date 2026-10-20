# -*- coding: utf-8 -*-
"""
多模型意图标注审核结果对比脚本（意图版，复用缺陷分级 compare_reviews.py 的思路）。

用法:
    # 1) 生成盲审输入文件 intent_review_input.md（从 qa_closed_intent.py）
    python intent_compare_reviews.py --make-input

    # 2) 对比多个模型的审核结果 CSV
    python intent_compare_reviews.py modelA.csv modelB.csv [modelC.csv ...]

输入 CSV 格式 (UTF-8 带 BOM, 列顺序固定):
    意图,序号,text,判定,纠正
    例如: 问答,2,母线温度多高算超了呀？,✓,
          异常处置,5,互感器油位低了咋整呗？,✗,异常处置

每条记录用 "意图-序号" 作为唯一键。
判定列只接受 ✓/✗ (其他值归为无效)。

输出:
    1) 两两一致率矩阵
    2) 逐条分歧清单 (哪些模型判了不同结果)
    3) 共识判 ✗ 的条目 (所有模型都认为标注错)
    4) 各模型 ✓/✗ 统计
"""
import csv
import os
import sys
from itertools import combinations
from pathlib import Path

EVAL = Path(__file__).resolve().parent
QA = EVAL / "qa_closed_intent.py"
INPUT = EVAL / "intent_review_input.md"


def load_qa() -> list[dict]:
    ns: dict = {}
    exec(QA.read_text(encoding="utf-8"), ns)
    return list(ns["CLOSED_INTENT"])


def make_input() -> None:
    """从 qa_closed_intent.py 生成盲审输入文件（按意图分组、组内从 1 编号）。"""
    rows = load_qa()
    by_intent: dict[str, list[dict]] = {}
    for r in rows:
        by_intent.setdefault(r["intent"], []).append(r)

    parts = [
        "# 意图识别闭卷评测 · 盲审输入\n\n",
        "> 共 {} 条。请按任务指令逐条判断自动标注的意图是否正确，输出 CSV。\n".format(len(rows)),
    ]
    for intent in ("问答", "状态查询", "异常处置", "工单生成", "其他"):
        items = by_intent.get(intent, [])
        if not items:
            continue
        parts.append(f"\n## {intent}（{len(items)} 条）\n\n")
        parts.append("| # | 意图 | 口语问句 text |\n")
        parts.append("|---|---|---|\n")
        for i, r in enumerate(items, 1):
            parts.append(f"| {i} | {r['intent']} | {r['text']} |\n")
    INPUT.write_text("".join(parts), encoding="utf-8")
    print(f"已生成盲审输入：{INPUT}（共 {len(rows)} 条）")


def load(path):
    """读取一个模型的审核结果 CSV，返回 {key: (判定, 纠正)}"""
    d = {}
    with open(path, encoding="utf-8-sig", newline="") as f:
        reader = csv.reader(f)
        next(reader, None)  # 跳过表头
        for row in reader:
            if len(row) < 4:
                continue
            intent, idx = row[0].strip(), row[1].strip()
            verdict = row[3].strip()
            corr = row[4].strip() if len(row) > 4 else ""
            if not intent or not idx:
                continue
            d[f"{intent}-{idx}"] = (verdict, corr)
    return d


def model_name(path):
    return os.path.splitext(os.path.basename(path))[0]


def compare(paths):
    models = {model_name(p): load(p) for p in paths}
    all_keys = set()
    for m in models.values():
        all_keys |= set(m.keys())
    keys = sorted(all_keys, key=lambda k: (k.split("-")[0], int(k.split("-")[1])))

    # 1) 两两一致率
    print("=== 1) 两两一致率 (仅比较判定列) ===")
    for a, b in combinations(models, 2):
        common = [k for k in keys if k in models[a] and k in models[b]]
        if not common:
            print(f"{a} vs {b}: 无共同条目")
            continue
        agree = sum(1 for k in common if models[a][k][0] == models[b][k][0])
        print(f"{a} vs {b}: {agree}/{len(common)} = {agree/len(common)*100:.1f}%")

    # 2) 逐条分歧
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

    # 3) 共识判 ✗（标注错）
    print("\n=== 3) 共识判 ✗ 的条目 (所有模型都认为标注错) ===")
    any_x = False
    for k in keys:
        vs = [models[m][k][0] for m in models if k in models[m]]
        if vs and all(v == "✗" for v in vs):
            any_x = True
            corr = set(models[m][k][1] for m in models if k in models[m])
            print(f"  {k}: 纠正建议={', '.join(c for c in corr if c)}")
    if not any_x:
        print("  (无)")

    # 4) 各模型统计
    print("\n=== 4) 各模型 ✓/✗ 统计 ===")
    for m in models:
        vals = [v[0] for v in models[m].values()]
        ok = sum(1 for v in vals if v == "✓")
        ng = sum(1 for v in vals if v == "✗")
        other = len(vals) - ok - ng
        extra = f", 无效={other}" if other else ""
        print(f"  {m}: 总{len(vals)} 条, ✓={ok}, ✗={ng}{extra}")


def main():
    if len(sys.argv) >= 2 and sys.argv[1] == "--make-input":
        make_input()
        return
    paths = sys.argv[1:]
    if len(paths) < 2:
        print(__doc__)
        print("错误: 至少需要 2 个 CSV 文件才能对比。")
        return
    compare(paths)


if __name__ == "__main__":
    main()
