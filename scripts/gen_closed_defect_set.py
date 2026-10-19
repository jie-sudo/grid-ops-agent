"""生成「闭卷口语缺陷评测集」：LLM 把缺陷库条目改写成运维口语，自动保留等级。

为什么需要它：现有评测用缺陷库原文当输入（开卷），会系统性高估命中率——
真实运维人员说「塔子锈得厉害」，和库里的「杆塔镀锌层脱落、开裂，塔材严重锈蚀」
文字根本对不上。本脚本用 LLM 把库条目改写成口语，产出「口语描述 → 等级」的闭卷评测集，
等级为自动标注，需人工抽检 10%~20% 纠错。

用法：
    python scripts/gen_closed_defect_set.py --per-level 5    # 快速试跑
    python scripts/gen_closed_defect_set.py --per-level 100  # 每级 100，共 300
"""
from __future__ import annotations

import argparse
import random
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import yaml

from app.engine.llm import LLMClient, LLMError

RULES = Path(__file__).resolve().parents[1] / "rules"
OUT = Path(__file__).resolve().parents[1] / "eval" / "qa_closed_defect.py"


def load() -> list[dict]:
    records = []
    for name in ("defect_library.yaml", "defect_library_1906.yaml"):
        p = RULES / name
        if p.exists():
            records += yaml.safe_load(p.read_text(encoding="utf-8")).get("defects", [])
    return records


def sample_by_level(records: list[dict], per_level: int) -> list[dict]:
    rng = random.Random(42)
    by_level: dict[str, list[dict]] = {}
    for r in records:
        by_level.setdefault(r["level"], []).append(r)
    samples = []
    for lvl in ("一般", "严重", "危急"):
        pool = by_level.get(lvl, [])
        samples += rng.sample(pool, min(per_level, len(pool)))
    return samples


def rewrite(llm: LLMClient, defect: str, basis: str) -> str | None:
    basis_line = f"\n分类依据：{basis}\n" if basis else ""
    prompt = (
        "你是电网运维专家。请把下面的缺陷描述（及其分类依据，如有），改写成「一线运维人员巡查时口头汇报」的一句口语。\n\n"
        "要求：\n"
        "1. 把「缺陷现象」和「分类依据里的程度/结论信息」都融合进一句口语，"
        "忠实保留原缺陷的现象和严重程度，不得改变事实。\n"
        "2. 原文里的数值（百分比/温度/尺寸等）要保留，但可换成口语说法（如「≥3%」可说「超过三个点」）。\n"
        "3. 严禁出现任何等级或程度判断词（如「一般/严重/危急/紧急/轻微/挺严重/很严重」），"
        "也不要出现「缺陷等级是XX」「XX缺陷」「情况危急」这类说法——口头汇报只描述现象和客观情况，不下等级结论。\n"
        "4. 只输出那一句口语，不要解释、不要引号、不要多余内容。\n\n"
        f"原文：{defect}"
        + basis_line
        + "\n"
    )
    try:
        out = llm.chat(
            [{"role": "user", "content": prompt}],
            temperature=0.3,
        )
        return out.strip()
    except LLMError:
        return None


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--per-level", type=int, default=100)
    args = ap.parse_args()

    records = load()
    samples = sample_by_level(records, args.per_level)
    llm = LLMClient()
    print(f"采样 {len(samples)} 条（每级 {args.per_level}），开始改写 ...\n")

    rows: list[dict] = []
    failed = 0
    for i, r in enumerate(samples, 1):
        desc = rewrite(llm, r.get("defect", ""), r.get("basis", ""))
        if desc is None:
            failed += 1
        else:
            rows.append({
                "desc": desc,
                "level": r["level"],
                "device_type": r.get("device_type"),
                "src_defect": r.get("defect", ""),
            })
        if i % 20 == 0:
            _write_out(rows)
            print(f"  进度 {i}/{len(samples)}（失败 {failed}，已保存 {len(rows)}）", flush=True)

    _write_out(rows)

    print(f"\n完成：成功 {len(rows)} 条，失败 {failed} 条")
    print(f"已写入 {OUT}")
    usage = llm.get_usage()
    print(f"token 用量：{usage}")


def _write_out(rows: list[dict]) -> None:
    """增量写文件：中断也不丢已改写的结果。"""
    header = (
        '"""闭卷口语缺陷评测集：LLM 从缺陷库改写生成，等级为自动标注（需人工抽检 10%~20% 纠错）。\n\n'
        "用途：评测缺陷分级在真实口语描述下的命中率（开卷评测用库原文，会高估）。\n"
        "desc=运维口语描述；level=自动标注等级；src_defect=改写来源（供抽检对照）。\n"
        '"""\n\n'
        "CLOSED_DEFECT = [\n"
    )
    body = ""
    for r in rows:
        body += (
            "    {\n"
            f"        \"desc\": {r['desc']!r},\n"
            f"        \"level\": {r['level']!r},\n"
            f"        \"device_type\": {r['device_type']!r},\n"
            f"        \"src_defect\": {r['src_defect']!r},\n"
            "    },\n"
        )
    OUT.write_text(header + body + "]\n", encoding="utf-8")


if __name__ == "__main__":
    main()
