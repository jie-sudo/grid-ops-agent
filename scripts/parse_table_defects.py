"""解析百度表格识别输出的 JSON → 输变电缺陷库记录。

输入：scripts/ocr_table_baidu.py 输出的 table_json/*.json（每页一个，含 tables_result）
输出：结构化缺陷记录列表（可存 YAML，格式对齐 745 的 defect_library）

Q/GDW 1906 表 A.1 结构：
    序号 | 设备类型 | 设备种类 | 部件 | 部件种类 | 部位 | 缺陷描述 | 分类依据 | 缺陷分类
合并单元格（设备类型/种类/部件）跨页时，续页这些列为空，需跨页累积。

用法：python scripts/parse_table_defects.py --dir 资料/table_json --out rules/defect_library_1906.yaml
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import yaml

# 列索引（基于表头识别结果）
COL_SEQ = 0          # 序号
COL_DEV_TYPE = 2     # 设备类型
COL_DEV_KIND = 3     # 设备种类
COL_COMP = 4         # 部件
COL_PART = 6         # 部位
COL_DEFECT = 7       # 缺陷描述
COL_BASIS = 8        # 分类依据
COL_LEVEL = 9        # 缺陷分类


def _norm_level(s: str) -> str:
    for k in ("危急", "严重", "一般"):
        if k in s:
            return k
    return ""  # 不是有效等级（如表头行"缺陷分类"），返回空以跳过


def cells_to_grid(cells: list[dict]) -> list[list[str]]:
    if not cells:
        return []
    n_rows = max(c.get("row_end", c.get("row_start", 0)) for c in cells) + 1
    n_cols = max(c.get("col_end", c.get("col_start", 0)) for c in cells) + 1
    grid = [["" for _ in range(n_cols)] for _ in range(n_rows)]
    for c in cells:
        w = c.get("words", "").replace("\n", "")
        for r in range(c.get("row_start", 0), c.get("row_end", 0) + 1):
            for col in range(c.get("col_start", 0), c.get("col_end", 0) + 1):
                if not grid[r][col]:
                    grid[r][col] = w
    return grid


def _get(row: list[str], idx: int) -> str:
    return row[idx].strip() if idx < len(row) else ""


def parse_table_json(json_files: list[Path]) -> list[dict]:
    """解析所有表格 JSON，返回缺陷记录（带跨页累积的上下文）。"""
    records: list[dict] = []
    ctx = {"dev_type": "", "dev_kind": "", "comp": ""}
    for jp in sorted(json_files):
        data = json.loads(jp.read_text(encoding="utf-8"))
        for table in data.get("tables_result") or []:
            grid = cells_to_grid(table.get("body") or [])
            for row in grid:
                defect = _get(row, COL_DEFECT)
                level = _norm_level(_get(row, COL_LEVEL))
                if not (defect and level):
                    continue  # 表头行/非数据行：跳过，不污染跨页上下文
                dev_type = _get(row, COL_DEV_TYPE)
                dev_kind = _get(row, COL_DEV_KIND)
                comp = _get(row, COL_COMP)
                basis = _get(row, COL_BASIS)
                # 合并单元格跨页：有值就更新上下文，否则沿用
                if dev_type:
                    ctx["dev_type"] = dev_type
                if dev_kind:
                    ctx["dev_kind"] = dev_kind
                if comp:
                    ctx["comp"] = comp
                records.append({
                    "device_type": ctx["dev_type"],
                    "device_kind": ctx["dev_kind"],
                    "component": ctx["comp"],
                    "part": _get(row, COL_PART),
                    "defect": defect,
                    "basis": basis,
                    "level": level,
                })
    return records


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dir", default=str(Path(__file__).resolve().parents[2] / "资料" / "table_json"))
    ap.add_argument("--out", default=str(Path(__file__).resolve().parents[1] / "rules" / "defect_library_1906.yaml"))
    args = ap.parse_args()

    files = sorted(Path(args.dir).glob("*.json"))
    if not files:
        sys.exit(f"{args.dir} 里没有 JSON，先跑 ocr_table_baidu.py 全量")

    records = parse_table_json(files)
    data = {"version": "1.0", "source": "Q/GDW 1906-2013 输变电一次设备缺陷分类标准", "defects": records}
    Path(args.out).write_text(yaml.safe_dump(data, allow_unicode=True, sort_keys=False), encoding="utf-8")
    print(f"生成 {args.out}：{len(records)} 条缺陷记录")


if __name__ == "__main__":
    main()
