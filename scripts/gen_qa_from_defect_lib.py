"""从结构化缺陷库自动生成检索评估集（方案 A）。

对每条缺陷记录，用缺陷描述生成问题、取描述里"在知识库 chunk 中真实存在"的最长前缀子串
做 hint（sanity check：hint 必须能被检索到，否则过滤），输出 eval/qa_generated.py。
"""
from __future__ import annotations

import json
import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import yaml

from app.data.ocr_clean import clean_ocr_text

RULES_DIR = Path(__file__).resolve().parents[1] / "rules"
MATERIAL_DIR = Path(__file__).resolve().parents[2] / "资料"
OCR_DIR = MATERIAL_DIR / "ocr_text"
OUT = Path(__file__).resolve().parents[1] / "eval" / "qa_generated.py"

TEMPLATES = [
    "{defect}属于什么缺陷等级？",
    "{defect}是什么等级？",
    "判定为{defect}，属于哪级缺陷？",
    "{defect}应定为什么等级？",
]


def load_defects() -> list[dict]:
    records = []
    for name in ("defect_library.yaml", "defect_library_1906.yaml"):
        p = RULES_DIR / name
        if p.exists():
            records += yaml.safe_load(p.read_text(encoding="utf-8")).get("defects", [])
    return records


def build_all_text() -> str:
    parts = []
    for p in sorted(OCR_DIR.glob("*.txt")):
        if p.stem.endswith((" (1)", " (2)")):
            continue
        parts.append(clean_ocr_text(p.read_text(encoding="utf-8")))
    return "\n".join(parts)


def make_hint(defect: str, all_text: str) -> str | None:
    d = defect.strip()
    # 找最长的"在知识库中真实存在"的前缀子串（避开 OCR 断行处）
    for length in range(min(len(d), 20), 3, -1):
        sub = d[:length]
        if sub in all_text:
            return sub
    return None


def main() -> None:
    rng = random.Random(42)
    all_text = build_all_text()
    records = load_defects()

    qa: list[dict] = []
    for r in records:
        defect = (r.get("defect") or "").strip()
        if len(defect) < 4:
            continue
        hint = make_hint(defect, all_text)
        if not hint:
            continue
        q = rng.choice(TEMPLATES).format(defect=defect[:30])
        qa.append({"q": q, "hint": hint})

    # 去重（同 q+hint）
    seen: set[tuple] = set()
    unique = []
    for x in qa:
        k = (x["q"], x["hint"])
        if k not in seen:
            seen.add(k)
            unique.append(x)

    OUT.write_text(
        "QA_GENERATED = " + json.dumps(unique, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(f"从 {len(records)} 条缺陷记录生成 {len(unique)} 题 -> {OUT}")


if __name__ == "__main__":
    main()
