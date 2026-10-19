"""miss 归因：分析 rerank 后未命中的题，拆成「召回 miss / 排序 miss」，定位根因。

用法（SAM2 环境）：python scripts/analyze_miss.py --sample 300
"""
from __future__ import annotations

import argparse
import random
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.data.kb import chunk_structured
from app.data.ocr_clean import clean_ocr_text
from app.data.retrieval import keyword_rank, rrf_fuse

MATERIAL_DIR = Path(__file__).resolve().parents[2] / "资料"
OCR_DIR = MATERIAL_DIR / "ocr_text"


def collect() -> list[str]:
    chunks = []
    if OCR_DIR.exists():
        for p in sorted(OCR_DIR.glob("*.txt")):
            if p.stem.endswith((" (1)", " (2)")):
                continue
            clean = clean_ocr_text(p.read_text(encoding="utf-8"))
            chunks.extend(chunk_structured(clean))
    return chunks


def first_rank(order, chunks, hint, limit=200):
    """hint 在 order 里最早出现的排名（1 起），超过 limit 或找不到返回 None。"""
    for r, idx in enumerate(order[:limit], 1):
        if hint in chunks[idx]:
            return r
    return None


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--sample", type=int, default=300)
    args = ap.parse_args()

    from eval.qa_set import QA_SET
    from eval.qa_generated import QA_GENERATED
    from sentence_transformers import SentenceTransformer

    from app.data.rerank import rerank

    all_qa = QA_SET + QA_GENERATED
    rng = random.Random(42)
    if args.sample < len(all_qa):
        all_qa = rng.sample(all_qa, args.sample)

    chunks = collect()
    questions = [q["q"] for q in all_qa]
    hints = [q["hint"] for q in all_qa]
    n = len(all_qa)

    model = SentenceTransformer("BAAI/bge-small-zh-v1.5")
    chunk_embs = model.encode(chunks, normalize_embeddings=True, show_progress_bar=True)
    q_embs = model.encode(questions, normalize_embeddings=True)
    import numpy as np

    sims = q_embs @ chunk_embs.T

    misses = []
    for i in range(n):
        vec_order = list(np.argsort(-sims[i]))
        key_order = keyword_rank(questions[i], chunks, top_k=2000)
        hyb30 = rrf_fuse([vec_order[:200], key_order[:200]], weights=[1.0, 2.0])[:30]
        rr5 = rerank(questions[i], [chunks[j] for j in hyb30], top_k=5)
        rr5_idx = [hyb30[j] for j in rr5]

        if first_rank(rr5_idx, chunks, hints[i], 5):
            continue  # 命中，跳过

        hyb_rank = first_rank(hyb30, chunks, hints[i], 30)
        vec_rank = first_rank(vec_order, chunks, hints[i], 2000)
        key_rank = first_rank(key_order, chunks, hints[i], 2000)
        misses.append({
            "hint_len": len(hints[i]),
            "src": "745" if any("745" in c for c in [chunks[j] for j in range(len(chunks)) if hints[i] in chunks[j]][:1]) else ("1906" if any("1906" in c for c in [chunks[j] for j in range(len(chunks)) if hints[i] in chunks[j]][:1]) else "其他"),
            "hyb_rank": hyb_rank,
            "vec_rank": vec_rank,
            "key_rank": key_rank,
        })

    recall_miss = [m for m in misses if m["hyb_rank"] is None]
    rank_miss = [m for m in misses if m["hyb_rank"] is not None]

    print(f"总 {n} 题，miss {len(misses)} 题（{len(misses)/n:.1%}）")
    print(f"  召回 miss（不在混合 top-30）: {len(recall_miss)}")
    print(f"  排序 miss（在 top-30，rerank 没提到 top-5）: {len(rank_miss)}\n")

    print("== 召回 miss 的向量/关键词排名（None=2000 名内都没召回）==")
    print(f"  hint长度分布: {dict(Counter(m['hint_len'] for m in recall_miss))}")
    print(f"  来源分布: {dict(Counter(m['src'] for m in recall_miss))}")
    print(f"  向量排名分布: {dict(Counter(m['vec_rank'] for m in recall_miss))}")
    print(f"  关键词排名分布: {dict(Counter(m['key_rank'] for m in recall_miss))}")

    print("\n== 排序 miss（rerank 没提上来）==")
    print(f"  hint长度分布: {dict(Counter(m['hint_len'] for m in rank_miss))}")
    print(f"  混合排名分布: {dict(Counter(m['hyb_rank'] for m in rank_miss))}")


if __name__ == "__main__":
    main()
