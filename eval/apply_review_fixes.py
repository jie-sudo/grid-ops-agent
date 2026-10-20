# -*- coding: utf-8 -*-
"""
应用多模型盲审的纠正，写回评测集 qa_closed_intent.py。

逻辑：
- 共识判 ✗（所有模型都 ✗ 且纠正一致）→ 自动把该条 intent 改为纠正值。
- 分歧条目（2:1 等）→ 打印出来，人工拍板后用 --fix 手动指定。

用法：
    python apply_review_fixes.py deepseek.csv GLM5.2.csv MiniMax.csv
    python apply_review_fixes.py deepseek.csv GLM5.2.csv MiniMax.csv --fix "问答-86:异常处置" "问答-131:异常处置"
"""
import argparse
import csv
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
QA = Path(__file__).resolve().parent / "qa_closed_intent.py"


def load_csv(path):
    d = {}
    with open(path, encoding="utf-8-sig", newline="") as f:
        for row in csv.reader(f):
            if len(row) < 5 or row[0].strip() == "意图":
                continue
            d[f"{row[0].strip()}-{row[1].strip()}"] = (row[3].strip(), row[4].strip())
    return d


def load_qa():
    ns: dict = {}
    exec(QA.read_text(encoding="utf-8"), ns)
    return list(ns["CLOSED_INTENT"])


def write_qa(rows):
    header = (
        '"""闭卷口语意图评测集：LLM 直接生成（强制禁用触发关键词 + 强制不重复 + 去重），意图为自动标注，需 100% 人工审核。\n\n'
        "用途：评测意图识别在「不带触发关键词」的一线口语下的准确率（开卷用规范问句，会高估规则层）。\n"
        "text=口语问句；intent=自动标注意图；src=生成方式（供追溯）。\n"
        '"""\n\n'
        "CLOSED_INTENT = [\n"
    )
    body = ""
    for r in rows:
        body += (
            "    {\n"
            f"        \"text\": {r['text']!r},\n"
            f"        \"intent\": {r['intent']!r},\n"
            f"        \"src\": {r['src']!r},\n"
            "    },\n"
        )
    QA.write_text(header + body + "]\n", encoding="utf-8")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("csvs", nargs="+", help="多个模型的审核 CSV")
    ap.add_argument("--fix", action="append", default=[], help="人工纠正，格式 意图-序号:新意图，可多次")
    args = ap.parse_args()

    models = {p: load_csv(p) for p in args.csvs}
    all_keys = set()
    for d in models.values():
        all_keys |= set(d.keys())

    # 共识判 ✗（所有模型都 ✗ 且纠正一致）
    consensus = {}
    for k in sorted(all_keys):
        verdicts = [models[p].get(k, ("缺失", "")) for p in models]
        if all(v[0] == "✗" for v in verdicts):
            corrs = {v[1] for v in verdicts if v[1]}
            if len(corrs) == 1:
                consensus[k] = corrs.pop()

    # 分歧报告（不自动改）
    diverged = []
    for k in sorted(all_keys):
        vs = {p: models[p].get(k, ("缺失", ""))[0] for p in models}
        if len(set(vs.values())) > 1:
            diverged.append((k, vs))

    if diverged:
        print("=== 分歧条目（未自动改，需人工拍板，可用 --fix 指定）===")
        for k, vs in diverged:
            print(f"  {k}: " + " | ".join(f"{p}={v}" for p, v in vs.items()))
    else:
        print("无分歧条目。")

    fixes = dict(consensus)
    for item in args.fix:
        if ":" in item:
            k, v = item.split(":", 1)
            fixes[k.strip()] = v.strip()

    if not fixes:
        print("\n没有要应用纠正的条目。")
        return

    rows = load_qa()
    by_intent = defaultdict(list)
    for r in rows:
        by_intent[r["intent"]].append(r)

    applied = 0
    for k, new_intent in sorted(fixes.items()):
        intent, idx = k.split("-")
        idx = int(idx)
        target = by_intent[intent][idx - 1]
        old = target["intent"]
        if old != new_intent:
            target["intent"] = new_intent
            applied += 1
            print(f"  纠正 {k}: {target['text']}  [{old}→{new_intent}]")

    new_rows = []
    for intent in ("问答", "状态查询", "异常处置", "工单生成", "其他"):
        new_rows.extend(by_intent[intent])
    write_qa(new_rows)
    print(f"\n已应用 {applied} 条纠正，写回 {QA}")


if __name__ == "__main__":
    main()
