"""生成「闭卷口语缺陷评测集」：LLM 把缺陷库条目改写成运维口语（强制同义替换），自动保留等级。

为什么需要它：现有评测用缺陷库原文当输入（开卷），会系统性高估命中率。本脚本用 LLM
把库条目改写成「一线工人口语」（不得照抄原文现象词，强制同义替换），产出
「口语描述 → 等级」的闭卷评测集。等级为自动标注，**需 100% 人工审核**——
同时生成 `eval/qa_closed_defect_review.md` 审核清单，逐条对照 src_defect 核对。

用法：
    python scripts/gen_closed_defect_set.py --per-level 5             # 快速试跑
    python scripts/gen_closed_defect_set.py --per-level 100           # 每级 100，共 300
    python scripts/gen_closed_defect_set.py --per-level 60 --level 危急  # 只补危急级
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
REVIEW = Path(__file__).resolve().parents[1] / "eval" / "qa_closed_defect_review.md"


def load() -> list[dict]:
    records = []
    for name in ("defect_library.yaml", "defect_library_1906.yaml"):
        p = RULES / name
        if p.exists():
            records += yaml.safe_load(p.read_text(encoding="utf-8")).get("defects", [])
    return records


def load_existing() -> tuple[list[dict], set[tuple[str, str]]]:
    """读已有评测集，返回 (已有条目, 已生成的 (src_defect, level) 集合)，用于增量续跑不重复。"""
    if not OUT.exists():
        return [], set()
    ns: dict = {}
    exec(OUT.read_text(encoding="utf-8"), ns)
    existing = ns.get("CLOSED_DEFECT", [])
    done = {(r.get("src_defect", ""), r.get("level", "")) for r in existing}
    return existing, done


def sample_by_level(records: list[dict], per_level: int, level: str | None = None, exclude: set | None = None) -> list[dict]:
    rng = random.Random(42)
    by_level: dict[str, list[dict]] = {}
    for r in records:
        by_level.setdefault(r["level"], []).append(r)
    levels = [level] if level else ("一般", "严重", "危急")
    exclude = exclude or set()
    samples = []
    for lvl in levels:
        pool = [r for r in by_level.get(lvl, []) if (r.get("defect", ""), lvl) not in exclude]
        samples += rng.sample(pool, min(per_level, len(pool)))
    return samples


def rewrite(llm: LLMClient, defect: str, basis: str) -> str | None:
    basis_line = f"\n分类依据：{basis}\n" if basis else ""
    prompt = (
        "你是电网运维专家。请把下面的缺陷描述，改写成「一线运维人员巡查时口头汇报」的一句话口语。\n\n"
        "关键要求（必须遵守）：\n"
        "1. 用一线工人的口语说法，不要用书面术语——缺陷现象的关键词必须换成口语同义说法，"
        "例如「发热/过热」说「烫手/摸着发烫/温度高」，「渗漏/渗油」说「漏油/往外渗」，「锈蚀」说「生锈/锈得掉渣」，"
        "「破损/开裂」说「破了/裂了口子」，「鼓肚」说「鼓包了」，「放电」说「打火/滋滋响」。\n"
        "2. 不得照抄原文里的缺陷现象词（必须换口语说法），但设备名称（变压器/导线/开关柜等）可以保留。\n"
        "3. 忠实保留原文的缺陷现象和严重程度（轻微/严重/危急的程度信息），不得改变事实、不得加重或减轻。\n"
        "4. 原文里的数值要保留，但口语化（如「≥3%」说「超了三个点」）。\n"
        "5. 严禁出现等级判断词（一般/严重/危急/紧急/轻微/挺严重）——口头汇报只描述现象和客观情况，不下等级结论。\n"
        "6. 只输出那一句口语，不要解释、不要引号、不要多余内容。\n\n"
        f"原文：{defect}"
        + basis_line
        + "\n"
    )
    try:
        out = llm.chat(
            [{"role": "user", "content": prompt}],
            temperature=0.5,  # 稍高温度让同义替换更多样
        )
        return out.strip()
    except LLMError:
        return None


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--per-level", type=int, default=100)
    ap.add_argument("--level", default=None, help="只生成某一级：一般/严重/危急")
    args = ap.parse_args()

    records = load()
    existing, done = load_existing()
    samples = sample_by_level(records, args.per_level, args.level, done)
    llm = LLMClient()
    print(f"已有 {len(existing)} 条；本次采样 {len(samples)} 条（每级 {args.per_level}，等级 {args.level or '全部'}），开始改写 ...\n")

    rows: list[dict] = list(existing)
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
            _write_review(rows)
            print(f"  进度 {i}/{len(samples)}（失败 {failed}，已保存 {len(rows)}）", flush=True)

    _write_out(rows)
    _write_review(rows)

    print(f"\n完成：成功 {len(rows)} 条，失败 {failed} 条")
    print(f"评测集：{OUT}")
    print(f"审核清单：{REVIEW}")
    usage = llm.get_usage()
    print(f"token 用量：{usage}")


def _write_out(rows: list[dict]) -> None:
    """增量写文件：中断也不丢已改写的结果。"""
    header = (
        '"""闭卷口语缺陷评测集：LLM 从缺陷库改写生成（强制同义替换），等级为自动标注，需 100% 人工审核。\n\n'
        "用途：评测缺陷分级在真实口语描述下的命中率（开卷评测用库原文，会高估）。\n"
        "desc=运维口语描述；level=自动标注等级；src_defect=改写来源（供逐条审核对照）。\n"
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


def _write_review(rows: list[dict]) -> None:
    """生成审核清单（markdown），供 100% 人工逐条审核。"""
    header = (
        "# 缺陷分级闭卷评测集 · 审核清单\n\n"
        "> desc 是 LLM 生成的口语，level 是自动标注（来自缺陷库），src_defect 是原文对照。\n"
        "> 请逐条审核：desc 是否忠实表达了 src_defect 的缺陷现象和严重程度（程度不加重、不减轻、数值不改、不张冠李戴）。\n"
        "> 忠实打 ✓；失真在「纠正」栏写正确等级或「删除」。\n\n"
    )
    by_level: dict[str, list[dict]] = {}
    for r in rows:
        by_level.setdefault(r["level"], []).append(r)
    parts = [header]
    for lvl in ("一般", "严重", "危急"):
        items = by_level.get(lvl, [])
        if not items:
            continue
        parts.append(f"## {lvl}（{len(items)} 条）\n\n")
        parts.append("| # | 口语描述 desc | 标注等级 | 原文对照 src_defect | ✓/✗ | 纠正 |\n")
        parts.append("|---|---|---|---|---|---|\n")
        for i, r in enumerate(items, 1):
            parts.append(
                f"| {i} | {r['desc']} | {r['level']} | {r['src_defect']} |  |  |\n"
            )
        parts.append("\n")
    REVIEW.write_text("".join(parts), encoding="utf-8")


if __name__ == "__main__":
    main()
