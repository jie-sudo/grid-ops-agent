# -*- coding: utf-8 -*-
"""
合并同一模型的多批审核 CSV 为一个总文件，并检测重复 key。

背景：728 条一次喂不下，按 5 个意图分 5 批让模型审，每批输出一段 CSV。
本脚本把多段合并成一个总 CSV（供 intent_compare_reviews.py 对比），并检测
「意图-序号」重复（说明模型某批输出有重复行、或两批序号重叠）。

用法：
    python merge_review_csv.py -o deepseek.csv deepseek_问答.csv deepseek_状态查询.csv deepseek_异常处置.csv deepseek_工单生成.csv deepseek_其他.csv

    -o 后是合并输出文件名；后面跟任意多个分片 CSV（按顺序）。
    每个分片第一行若是表头（含「判定」字样的行）会自动跳过。

输出：
    合并后的 CSV 写入 -o 指定文件；屏幕打印总行数 + 重复 key 警告。
"""
import csv
import sys
from pathlib import Path


def load_rows(path):
    """读一个分片 CSV，返回 (header, rows)。自动跳过表头行。"""
    rows = []
    with open(path, encoding="utf-8-sig", newline="") as f:
        reader = csv.reader(f)
        for row in reader:
            if not row or all(not c.strip() for c in row):
                continue
            # 表头特征：第一列是「意图」，且含「判定」列
            if row[0].strip() == "意图" or "判定" in row:
                continue
            rows.append(row)
    return rows


def main():
    args = sys.argv[1:]
    if "-o" not in args:
        print(__doc__)
        return
    oi = args.index("-o")
    out_path = args[oi + 1]
    parts = args[oi + 2:]
    if not parts:
        print(__doc__)
        return

    header = ["意图", "序号", "text", "判定", "纠正"]
    all_rows = []
    seen = {}  # key -> 第一次出现的行
    dup = []

    for p in parts:
        for row in load_rows(p):
            key = f"{row[0].strip()}-{row[1].strip()}"
            if key in seen:
                dup.append(key)
            else:
                seen[key] = row
            all_rows.append(row)

    # 去重写回：保留首次出现
    with open(out_path, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f)
        w.writerow(header)
        written = 0
        written_keys = set()
        for row in all_rows:
            key = f"{row[0].strip()}-{row[1].strip()}"
            if key in written_keys:
                continue
            written_keys.add(key)
            w.writerow(row)
            written += 1

    print(f"合并完成：{written} 行 → {out_path}")
    if dup:
        print(f"⚠️ 检测到 {len(dup)} 个重复 key（已去重，保留首次出现）：")
        for k in dup[:20]:
            print(f"    {k}")
    else:
        print("无重复 key。")


if __name__ == "__main__":
    main()
