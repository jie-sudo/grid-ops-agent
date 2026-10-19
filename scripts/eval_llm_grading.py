"""LLM 缺陷定级评测：零样本 vs 检索增强，在闭卷口语评测集上测准确率。

背景：确定性 bigram/关键词在闭卷口语下命中率仅 1%，放宽 C1 让 LLM 参与定级。
本脚本验证「LLM 定级」这条路能否把命中率提上来。

用法：
    python scripts/eval_llm_grading.py --mode zero_shot --sample 20
    python scripts/eval_llm_grading.py --mode zero_shot            # 全量 200
    python scripts/eval_llm_grading.py --mode rag --sample 20      # 检索增强
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import yaml

from app.data.defect_lib import _cjk_bigrams
from app.engine.llm import LLMClient, LLMError

RULES = Path(__file__).resolve().parents[1] / "rules"


def load_library() -> list[dict]:
    records = []
    for name in ("defect_library.yaml", "defect_library_1906.yaml"):
        p = RULES / name
        if p.exists():
            records += yaml.safe_load(p.read_text(encoding="utf-8")).get("defects", [])
    return records


def recall_topk(desc: str, records: list[dict], k: int = 10, device_type: str | None = None):
    """bigram 召回 top-k（不设 threshold，取覆盖度最高的 k 条）。"""
    terms = _cjk_bigrams(desc)
    if not terms:
        return []
    filtered = records
    if device_type:
        f = [
            r for r in records
            if device_type in (
                (r.get("device_type") or "") + (r.get("device_category") or "")
                + (r.get("device_kind") or "") + (r.get("component") or "")
            )
        ]
        if f:
            filtered = f
    scored = []
    for rec in filtered:
        hay = " ".join([
            rec.get("component", ""), rec.get("part", ""),
            rec.get("defect", ""), rec.get("basis", ""),
        ])
        score = sum(1 for t in terms if t in hay) / len(terms)
        scored.append((score, rec))
    scored.sort(key=lambda x: -x[0])
    return scored[:k]

DEF = (
    "缺陷三级定义（Q/GDW 745）：\n"
    "- 一般缺陷：不威胁设备安全运行或影响较小，可列入年/季检修计划消除。\n"
    "- 严重缺陷：威胁设备安全运行，但尚能坚持运行一段时间，需尽快（30 天内）消除。\n"
    "- 危急缺陷：随时可能造成事故，必须立即（24 小时内）处理。\n"
)


def load_closed():
    ns: dict = {}
    p = Path(__file__).resolve().parents[1] / "eval" / "qa_closed_defect.py"
    exec(p.read_text(encoding="utf-8"), ns)
    return ns["CLOSED_DEFECT"]


def llm_grade_zero(llm: LLMClient, desc: str) -> str | None:
    prompt = (
        "你是电网设备缺陷分级专家。按国网缺陷分级标准，判断下面缺陷属于哪一级。\n\n"
        + DEF
        + "\n只输出一个等级词（一般/严重/危急）；若信息不足无法判断，输出「无法判断」。不要解释。\n\n"
        f"缺陷描述：{desc}\n"
    )
    try:
        out = llm.chat([{"role": "user", "content": prompt}], temperature=0.0).strip()
    except LLMError:
        return None
    for lv in ("危急", "严重", "一般"):
        if lv in out:
            return lv
    return None  # 含「无法判断」或其他 → 降级


def llm_grade_rag(llm: LLMClient, desc: str, records: list[dict], device_type: str | None, k: int = 10) -> str | None:
    top = recall_topk(desc, records, k=k, device_type=device_type)
    seen = set()
    lines = []
    for score, rec in top:
        if score <= 0:
            continue
        d = rec.get("defect", "").strip()
        basis = (rec.get("basis") or "").strip()
        key = (d, basis)
        if key in seen:
            continue
        seen.add(key)
        label = d + (f"（依据：{basis}）" if basis else "")
        lines.append(f"- [{rec.get('level')}] {label}")
    if not lines:
        return None
    refs = "\n".join(lines)
    prompt = (
        "你是电网设备缺陷分级专家。你的任务是：从下面的「缺陷库相似条目」里，找出和目标缺陷描述"
        "最匹配的一条（描述的是同一缺陷现象、同一严重程度），直接输出那一条的等级。\n\n"
        "规则：\n"
        "1. 只做匹配，不要用自己的常识判断缺陷严重程度。即使某条库条目的等级和你的直觉不符，也照那条的等级输出。\n"
        "2. 注意目标描述里的程度词：「有点/轻微/略有」对应轻微的条目；「严重/厉害/穿/裂」对应严重的条目。\n"
        "3. 不要折中、不要猜。若确实找不到匹配的条目，输出「无法判断」。\n\n"
        + DEF
        + "\n缺陷库相似条目（按相似度排序）：\n"
        + refs
        + "\n\n目标缺陷描述：" + desc + "\n"
        "\n只输出一个等级词（一般/严重/危急/无法判断）。\n"
    )
    try:
        out = llm.chat([{"role": "user", "content": prompt}], temperature=0.0).strip()
    except LLMError:
        return None
    for lv in ("危急", "严重", "一般"):
        if lv in out:
            return lv
    return None


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--mode", choices=["zero_shot", "rag"], default="zero_shot")
    ap.add_argument("--sample", type=int, default=0)
    ap.add_argument("--k", type=int, default=10)
    args = ap.parse_args()

    data = load_closed()
    if args.sample:
        data = data[: args.sample]

    records = load_library() if args.mode == "rag" else []
    llm = LLMClient()
    hit = degrade = wrong = 0
    wrong_cases = []
    for i, r in enumerate(data, 1):
        if args.mode == "zero_shot":
            lv = llm_grade_zero(llm, r["desc"])
        else:
            lv = llm_grade_rag(llm, r["desc"], records, r["device_type"], k=args.k)
        if lv == r["level"]:
            hit += 1
        elif lv is None:
            degrade += 1
        else:
            wrong += 1
            wrong_cases.append((r["desc"], r["level"], lv))
        if i % 20 == 0:
            print(f"  进度 {i}/{len(data)} 命中{hit} 降级{degrade} 误判{wrong}", flush=True)

    n = len(data)
    print(f"\n[{args.mode}] 闭卷口语 {n} 条：")
    print(f"  命中 {hit} ({hit/n:.1%}) | 降级 {degrade} ({degrade/n:.1%}) | 误判 {wrong} ({wrong/n:.1%})")
    if wrong_cases:
        print("  误判样例：")
        for c in wrong_cases[:10]:
            print(f"    [{c[1]}→{c[2]}] {c[0]}")


if __name__ == "__main__":
    main()
