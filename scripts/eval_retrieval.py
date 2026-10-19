"""检索 Recall@K 评测：对比「纯向量」与「混合（向量+关键词）」两条路。

用法（SAM2 环境，需 sentence-transformers + 嵌入模型已下载）：
    python scripts/eval_retrieval.py

对每个问题分别算纯向量检索和混合检索的 top-K 命中，输出两列 Recall 对比，
验证混合检索能否救回纯向量在"语义竞争/表格碎片"下 miss 的题。
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.config import get_settings
from app.data.kb import chunk_structured
from app.data.ocr_clean import clean_ocr_text
from app.data.retrieval import keyword_rank, rrf_fuse

MATERIAL_DIR = Path(__file__).resolve().parents[2] / "资料"
OCR_DIR = MATERIAL_DIR / "ocr_text"


def collect() -> list[tuple[str, str]]:
    sources = []
    if OCR_DIR.exists():
        for p in sorted(OCR_DIR.glob("*.txt")):
            if not p.stem.endswith((" (1)", " (2)")):
                sources.append((p.stem, p.read_text(encoding="utf-8")))
    return sources


def find_rank(order: list[int], chunks: list[str], hint: str) -> int | None:
    for r, idx in enumerate(order, 1):
        if hint in chunks[idx]:
            return r
    return None


def main() -> None:
    from eval.qa_set import QA_SET
    from sentence_transformers import SentenceTransformer

    settings = get_settings()
    print(f"加载嵌入模型 {settings.embedding_model} ...")
    model = SentenceTransformer(settings.embedding_model)

    chunks: list[str] = []
    for stem, raw in collect():
        clean = clean_ocr_text(raw)
        if clean.strip():
            chunks.extend(chunk_structured(clean))

    print(f"共 {len(chunks)} 个 chunk，嵌入中...")
    chunk_embs = model.encode(chunks, normalize_embeddings=True, show_progress_bar=True)
    q_embs = model.encode([qa["q"] for qa in QA_SET], normalize_embeddings=True)

    import numpy as np
    sims = q_embs @ chunk_embs.T  # (n_q, n_chunks)

    print(f"\n{'问题':<32}{'向量':>6}{'混合':>6}   向量rank/混合rank")
    vec_hits = {"1": 0, "5": 0, "10": 0}
    hyb_hits = {"1": 0, "5": 0, "10": 0}
    for i, qa in enumerate(QA_SET):
        vec_order = list(np.argsort(-sims[i]))  # 向量序
        key_order = keyword_rank(qa["q"], chunks, top_k=200)
        hyb_order = rrf_fuse([vec_order[:200], key_order])[:10]

        vr = find_rank(vec_order[:10], chunks, qa["hint"])
        hr = find_rank(hyb_order, chunks, qa["hint"])
        for k in (1, 5, 10):
            if vr and vr <= k:
                vec_hits[str(k)] += 1
            if hr and hr <= k:
                hyb_hits[str(k)] += 1
        v = "✓" if vr and vr <= 5 else "—"
        h = "✓" if hr and hr <= 5 else "—"
        print(f"{qa['q'][:31]:<32}{v:>6}{h:>6}   #{vr or '—'}/#{hr or '—'}")

    n = len(QA_SET)
    print("-" * 64)
    for k in (1, 5, 10):
        print(f"Recall@{k}  向量 {vec_hits[str(k)]}/{n} = {vec_hits[str(k)]/n:.1%}   混合 {hyb_hits[str(k)]}/{n} = {hyb_hits[str(k)]/n:.1%}")


if __name__ == "__main__":
    main()
