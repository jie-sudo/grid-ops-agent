# -*- coding: utf-8 -*-
import re

INPUT = r"F:\通用agent\grid-ops-agent\eval\intent_review_input.md"
OUTPUT = r"F:\通用agent\grid-ops-agent\eval\intent_review_output.csv"

# 我的判定：序号在问答类中应判 ✗（纠正为异常处置）的集合
WRONG_IN_WENDA = {2, 47, 51, 55, 66, 67, 86, 87, 97, 126, 131, 134}

rows = []
current_section = None

with open(INPUT, "r", encoding="utf-8") as f:
    for line in f:
        line = line.rstrip("\n")
        # 识别分类标题
        m = re.match(r"^## (\S+)（\d+ 条）", line)
        if m:
            current_section = m.group(1)
            continue
        # 识别表格行: | # | 意图 | text |
        m = re.match(r"^\|\s*(\d+)\s*\|\s*(\S+)\s*\|\s*(.*?)\s*\|\s*$", line)
        if m:
            num = int(m.group(1))
            intent = m.group(2)
            text = m.group(3)
            rows.append((intent, num, text))

# 判定
out_lines = ["意图,序号,text,判定,纠正"]
for intent, num, text in rows:
    if intent == "问答" and num in WRONG_IN_WENDA:
        verdict = "✗"
        correct = "异常处置"
    else:
        verdict = "✓"
        correct = ""
    out_lines.append(f"{intent},{num},{text},{verdict},{correct}")

with open(OUTPUT, "w", encoding="utf-8") as f:
    f.write("\n".join(out_lines) + "\n")

print(f"总行数: {len(rows)}")
print(f"判 ✗ 数: {sum(1 for r in rows if (r[0]=='问答' and r[1] in WRONG_IN_WENDA))}")
print(f"输出: {OUTPUT}")
