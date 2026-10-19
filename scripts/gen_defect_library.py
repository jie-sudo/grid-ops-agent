"""生成结构化缺陷库 YAML：解析 Q/GDW 745 缺陷分类标准 → rules/defect_library.yaml。

用法：python scripts/gen_defect_library.py [--src <清洗后 txt 路径>]
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import yaml

from app.data.defect_lib import parse_defect_library
from app.data.ocr_clean import clean_ocr_text

DEFAULT_SRC = (
    Path(__file__).resolve().parents[2] / "资料" / "ocr_text" / "Q／GDW 745-2012 配电网设备缺陷分类标准.txt"
)
OUT = Path(__file__).resolve().parents[1] / "rules" / "defect_library.yaml"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--src", default=str(DEFAULT_SRC))
    args = ap.parse_args()

    clean = clean_ocr_text(Path(args.src).read_text(encoding="utf-8"))
    records = parse_defect_library(clean)
    data = {
        "version": "1.0",
        "source": "Q/GDW 745-2012 配电网设备缺陷分类标准",
        "defects": records,
    }
    OUT.write_text(
        yaml.safe_dump(data, allow_unicode=True, sort_keys=False),
        encoding="utf-8",
    )
    print(f"生成 {OUT}：{len(records)} 条缺陷记录")


if __name__ == "__main__":
    main()
