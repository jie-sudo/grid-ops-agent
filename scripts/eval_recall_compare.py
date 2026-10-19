"""向量召回 vs bigram 召回对比评测（闭卷口语缺陷集）。

验证两件事：
1. 向量召回能否救回 bigram 召不回的「纯同义替换」（如「烫手」→「发热」）——看 recall@k。
2. 各召回方式（bigram / 向量 / 混合）对 LLM 定级准确率的影响。

用法（Windows SAM2 环境，需 sentence-transformers + bge-small 模型已缓存）：
    python scripts/eval_recall_compare.py --sample 50   # 快速试跑
    python scripts/eval_recall_compare.py               # 全量 180
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import yaml

from app.config import get_settings
from app.data.defect_lib import recall_topk as recall_topk_bigram
from app.engine.llm import LLMClient, LLMError

RULES = Path(__file__).resolve().parents[1] / "rules"
CACHE = Path(__file__).resolve().parents[1] / "eval" / "defect_emb_cache.npz"

DEF = (
    "缺陷三级定义（Q/GDW 745）：\n"
    "- 一般缺陷：不威胁设备安全运行或影响较小，可列入年/季检修计划消除。\n"
    "- 严重缺陷：威胁设备安全运行，但尚能坚持运行一段时间，需尽快（30 天内）消除。\n"
    "- 危急缺陷：随时可能造成事故，必须立即（24 小时内）处理。\n"
)


def load_library() -> list[dict]:
    records = []
    for name in ("defect_library.yaml", "defect_library_1906.yaml"):
        p = RULES / name
        if p.exists():
            records += yaml.safe_load(p.read_text(encoding="utf-8")).get("defects", [])
    return records


def load_closed() -> list[dict]:
    ns: dict = {}
    p = Path(__file__).resolve().parents[1] / "eval" / "qa_closed_defect.py"
    exec(p.read_text(encoding="utf-8"), ns)
    return ns["CLOSED_DEFECT"]


def _filter_device(records: list[dict], device_type: str | None) -> list[dict]:
    if not device_type:
        return records
    f = [
        r for r in records
        if device_type in (
            (r.get("device_type") or "") + (r.get("device_category") or "")
            + (r.get("device_kind") or "") + (r.get("component") or "")
        )
    ]
    return f if f else records


def recall_topk_vector(desc, records, model, embs, k=10, device_type=None):
    """cos 相似度向量召回 top-k。"""
    q = model.encode([desc], normalize_embeddings=True)[0]
    filtered = _filter_device(records, device_type)
    idx_map = [records.index(r) for r in filtered]
    sims = embs[idx_map] @ q
    order = sims.argsort()[::-1][:k]
    return [(float(sims[i]), filtered[i]) for i in order]


def recall_topk_hybrid(desc, records, model, embs, k=10, device_type=None):
    """bigram + 向量 RRF 融合召回。"""
    b = recall_topk_bigram(desc, records, k=30, device_type=device_type)
    v = recall_topk_vector(desc, records, model, embs, k=30, device_type=device_type)
    scores: dict[int, float] = {}
    for rank, (_, rec) in enumerate(b, 1):
        idx = id(rec)
        scores[idx] = scores.get(idx, 0) + 1 / (60 + rank) * 1.0
    for rank, (_, rec) in enumerate(v, 1):
        idx = id(rec)
        scores[idx] = scores.get(idx, 0) + 1 / (60 + rank) * 2.0  # 向量权重更高（救同义）
    ranked = sorted(scores.items(), key=lambda x: -x[1])[:k]
    idx_to_rec = {}
    for _, rec in (b + v):
        idx_to_rec[id(rec)] = rec
    return [(s, idx_to_rec[i]) for i, s in ranked]


def llm_grade(desc, topk, llm):
    seen = set()
    lines = []
    for score, rec in topk:
        if score <= 0 and lines:
            continue
        d = (rec.get("defect") or "").strip()
        basis = (rec.get("basis") or "").strip()
        if (d, basis) in seen or not d:
            continue
        seen.add((d, basis))
        label = d + (f"（依据：{basis}）" if basis else "")
        lines.append((rec.get("level"), label))
    if not lines:
        return None
    refs = "\n".join(f"- [{lv}] {label}" for lv, label in lines)
    prompt = (
        "你是电网设备缺陷分级专家。你的任务是：从下面的「缺陷库相似条目」里，找出和目标缺陷描述"
        "最匹配的一条，直接输出那一条的等级。\n\n"
        "规则：\n"
        "1. 只做匹配，不要用自己的常识判断缺陷严重程度，照匹配条目的等级输出。\n"
        "2. 注意程度词：「有点/轻微/略有」对应轻微条目；「严重/厉害/穿/裂」对应严重条目。\n"
        "3. 不要折中、不要猜。找不到匹配条目时 level 填「无法判断」。\n\n"
        + DEF
        + "\n缺陷库相似条目：\n" + refs
        + "\n\n目标缺陷描述：" + desc + "\n"
        '\n只输出 JSON：{"level": "一般/严重/危急/无法判断"}。\n'
    )
    try:
        raw = llm.chat([{"role": "user", "content": prompt}], temperature=0.0).strip()
        if raw.startswith("```"):
            raw = raw.strip("`").lstrip("json").strip()
        import json

        lv = json.loads(raw).get("level")
    except (LLMError, ValueError, AttributeError):
        return None
    return lv if lv in ("一般", "严重", "危急") else None


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--sample", type=int, default=0)
    ap.add_argument("--skip-llm", action="store_true", help="只测 recall@k，不调 LLM")
    args = ap.parse_args()

    from sentence_transformers import SentenceTransformer

    settings = get_settings()
    model_name = settings.embedding_model or "BAAI/bge-small-zh-v1.5"
    print(f"加载嵌入模型 {model_name} ...")
    model = SentenceTransformer(model_name)

    records = load_library()
    data = load_closed()
    if args.sample:
        data = data[: args.sample]
    print(f"缺陷库 {len(records)} 条，闭卷评测 {len(data)} 条")

    # 预计算库向量（缓存）
    if CACHE.exists():
        import numpy as np

        embs = np.load(CACHE)["embs"]
        print(f"库向量缓存命中 {CACHE}（{embs.shape}）")
    else:
        import numpy as np

        print(f"嵌入缺陷库 {len(records)} 条 ...")
        texts = [r.get("defect", "") + (r.get("basis", "") or "") for r in records]
        embs = model.encode(texts, normalize_embeddings=True, show_progress_bar=True)
        np.savez(CACHE, embs=embs)
        print(f"缓存已写 {CACHE}")

    llm = LLMClient()

    print("\n=== recall@k：正确等级是否在召回集 ===")
    for k in (5, 10):
        for name, fn in (("bigram", lambda d, r, dt: recall_topk_bigram(d, r, k=k, device_type=dt)),
                         ("向量", lambda d, r, dt: recall_topk_vector(d, r, model, embs, k=k, device_type=dt)),
                         ("混合", lambda d, r, dt: recall_topk_hybrid(d, r, model, embs, k=k, device_type=dt))):
            hit = 0
            for r in data:
                top = fn(r["desc"], records, r["device_type"])
                if any(rec["level"] == r["level"] for _, rec in top):
                    hit += 1
            print(f"  {name:6} top-{k}: {hit}/{len(data)} ({hit/len(data):.1%})")

    if args.skip_llm:
        return

    print("\n=== LLM 定级准确率（各召回方式）===")
    for name, fn in (("bigram", lambda d, r, dt: recall_topk_bigram(d, r, k=10, device_type=dt)),
                     ("向量", lambda d, r, dt: recall_topk_vector(d, r, model, embs, k=10, device_type=dt)),
                     ("混合", lambda d, r, dt: recall_topk_hybrid(d, r, model, embs, k=10, device_type=dt))):
        hit = degrade = wrong = 0
        wc = []
        for r in data:
            top = fn(r["desc"], records, r["device_type"])
            lv = llm_grade(r["desc"], top, llm)
            if lv == r["level"]:
                hit += 1
            elif lv is None:
                degrade += 1
            else:
                wrong += 1
                wc.append((r["desc"], r["level"], lv))
        n = len(data)
        print(f"  {name:6}: 命中 {hit}({hit/n:.1%}) | 降级 {degrade}({degrade/n:.1%}) | 误判 {wrong}({wrong/n:.1%})")


if __name__ == "__main__":
    main()
