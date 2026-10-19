"""把百度表格 OCR 结果（table_json）重建成 1906 干净文本，替换本地 OCR 碎片。

本地 PaddleOCR 把 1906 的表格打碎成"绝缘电阻不\\n合格"，导致知识库 chunk 检索不到；
百度表格 OCR 返回单元格结构，重建成每行一条完整缺陷记录，替换碎片后再重新 ingest。

用法：python scripts/rebuild_1906_text.py
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scripts.parse_table_defects import parse_table_json

MATERIAL_DIR = Path(__file__).resolve().parents[2] / "资料"
TABLE_DIR = MATERIAL_DIR / "table_json"
OUT = MATERIAL_DIR / "ocr_text" / "Q_GDW 1906-2013 输变电一次设备缺陷分类标准 - 副本.txt"


def main() -> None:
    files = sorted(TABLE_DIR.glob("*.json"))
    if not files:
        sys.exit("table_json 为空，先跑 ocr_table_baidu.py 全量")

    records = parse_table_json(files)
    # 每条记录一行：设备类型/设备种类/部件/部位/缺陷描述/分类依据/等级
    lines = []
    for r in records:
        parts = [r["device_type"], r["device_kind"], r["component"], r["part"], r["defect"], r["basis"], r["level"]]
        lines.append(" ".join(p for p in parts if p and p not in ("设备类型", "设备种类", "部件")))

    OUT.write_text("\n".join(lines), encoding="utf-8")
    print(f"重建 {len(lines)} 条 → {OUT}")


if __name__ == "__main__":
    main()
