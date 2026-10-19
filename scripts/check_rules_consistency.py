"""规则库一致性自检：扫描缺陷库和关键词规则的潜在冲突。

检测项：
1. 缺陷库跨库冲突：同一缺陷描述（规范化）在 745/1906 两个库等级不一致；
2. 745 内部冲突：745 里同一描述出现不同等级（本不该有）；
3. 关键词 vs 缺陷库：关键词规则说某词是 X 级，但缺陷库含该词的记录是别的等级。

注意：1906 内部"同描述三档"是合法的（靠 basis/分类依据区分），不报。

用法：python scripts/check_rules_consistency.py
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import yaml

RULES = Path(__file__).resolve().parents[1] / "rules"


def norm(s: str) -> str:
    """规范化缺陷描述：去括号内容、标点、空白，用于聚合比较。"""
    s = re.sub(r"[（(][^)）]*[)）]", "", s or "")
    s = re.sub(r"[\s，。、；：%℃≤≥×±～—…·/\\,;:()[\]【】]+", "", s)
    return s


def load_defects() -> list[dict]:
    records = []
    for name in ("defect_library.yaml", "defect_library_1906.yaml"):
        p = RULES / name
        if p.exists():
            for r in yaml.safe_load(p.read_text(encoding="utf-8")).get("defects", []):
                r["_src"] = name
                records.append(r)
    return records


def main() -> None:
    records = load_defects()
    print(f"缺陷库 {len(records)} 条（745 + 1906）\n")

    # 按规范化缺陷描述分组
    by_defect: dict[str, list[dict]] = {}
    for r in records:
        d = norm(r.get("defect", ""))
        if len(d) >= 4:
            by_defect.setdefault(d, []).append(r)

    # 检测：同描述、等级不一致，且不是 1906 内部的 basis 区分
    cross_conflicts, intra_745 = [], []
    for d, rs in by_defect.items():
        levels = {r["level"] for r in rs}
        if len(levels) <= 1:
            continue
        srcs = {r["_src"] for r in rs}
        if len(srcs) > 1:  # 跨库
            cross_conflicts.append((d, rs))
        elif "defect_library.yaml" in srcs:  # 745 内部
            intra_745.append((d, rs))

    print(f"规范化后 {len(by_defect)} 个不同缺陷描述")
    print(f"[检测1] 跨库等级冲突: {len(cross_conflicts)} 处")
    for d, rs in cross_conflicts[:15]:
        info = " | ".join(f"{r['_src'].replace('.yaml','')}={r['level']}" for r in rs)
        print(f"    {d[:40]} → {info}")

    print(f"\n[检测2] 745 内部同描述不同等级（异常，应为 0）: {len(intra_745)} 处")
    for d, rs in intra_745[:10]:
        info = ", ".join(r["level"] for r in rs)
        print(f"    {d[:40]} → {info}")

    # 检测 3：关键词 vs 缺陷库
    kw_rules = yaml.safe_load((RULES / "defect_level.yaml").read_text(encoding="utf-8"))["keywords"]
    print("\n[检测3] 关键词规则 vs 缺陷库等级不一致：")
    found = 0
    for level, kws in kw_rules.items():
        for k in kws:
            hits = [r for r in records if k in (r.get("defect") or "")]
            if not hits:
                continue
            hit_levels = {r["level"] for r in hits}
            if hit_levels and hit_levels != {level}:
                found += 1
                if found <= 20:
                    print(f"    关键词[{k}] 规则={level}，但缺陷库含该词的记录等级={hit_levels}")
    if found == 0:
        print("    无（关键词规则和缺陷库一致）")
    else:
        print(f"    共 {found} 个关键词存在不一致")


if __name__ == "__main__":
    main()
