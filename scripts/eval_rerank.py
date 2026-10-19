"""Rerank 精排评测：对比「混合检索」vs「混合 + rerank 精排」的 Recall@K。

用法（SAM2 环境，需 sentence-transformers，reranker 模型下载走 HF 镜像）：
    $env:HF_ENDPOINT = "https://hf-mirror.com"
    $env:HF_HUB_DOWNLOAD_TIMEOUT = "120"
    python scripts/eval_rerank.py

输出：混合 R@5/R@10 vs rerank 后 R@5/R@10（重点看 R@5 有没有提升）。
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.data.kb import chunk_structured
from app.data.ocr_clean import clean_ocr_text
from app.data.retrieval import keyword_rank, rrf_fuse

MATERIAL_DIR = Path(__file__).resolve().parents[2] / "资料"
OCR_DIR = MATERIAL_DIR / "ocr_text"
EMBED_MODEL = "BAAI/bge-small-zh-v1.5"
RERANK_MODEL = "BAAI/bge-reranker-base"


def collect() -> list[tuple[str, str]]:
    sources = []
    if OCR_DIR.exists():
        for p in sorted(OCR_DIR.glob("*.txt")):
            if not p.stem.endswith((" (1)", " (2)")):
                sources.append((p.stem, p.read_text(encoding="utf-8")))
    return sources


def main() -> None:
    import argparse

    ap = argparse.ArgumentParser()
    ap.add_argument("--sample", type=int, default=300, help="从生成集随机采样 N 题（0=全部）")
    args = ap.parse_args()

    from eval.qa_set import QA_SET
    from eval.qa_generated import QA_GENERATED
    from sentence_transformers import SentenceTransformer

    from app.data.rerank import rerank

    all_qa = QA_SET + QA_GENERATED
    if args.sample and args.sample < len(all_qa):
        import random

        rng = random.Random(42)
        all_qa = rng.sample(all_qa, args.sample)

    chunks: list[str] = []
    for stem, raw in collect():
        clean = clean_ocr_text(raw)
        if clean.strip():
            chunks.extend(chunk_structured(clean))
    questions = [qa["q"] for qa in all_qa]
    hints = [qa["hint"] for qa in all_qa]
    n = len(all_qa)
    print(f"评估 {n} 题（共 {len(chunks)} chunk）")

    print(f"加载嵌入模型 {EMBED_MODEL} ...")
    model = SentenceTransformer(EMBED_MODEL)
    chunk_embs = model.encode(chunks, normalize_embeddings=True, show_progress_bar=True)
    q_embs = model.encode(questions, normalize_embeddings=True)
    import numpy as np

    sims = q_embs @ chunk_embs.T

    print(f"加载 reranker {RERANK_MODEL} ...")
    # 预热加载
    from app.data.rerank import get_reranker

    get_reranker(RERANK_MODEL)

    hybrid_hits = {"5": 0, "10": 0}
    rr_hits = {"5": 0, "10": 0}
    for i in range(n):
        vec_order = list(np.argsort(-sims[i]))
        key_order = keyword_rank(questions[i], chunks, top_k=200)
        hyb30 = rrf_fuse([vec_order[:200], key_order], weights=[1.0, 2.0])[:30]

        # 混合 R@5/R@10
        for r, idx in enumerate(hyb30, 1):
            if hints[i] in chunks[idx]:
                if r <= 5:
                    hybrid_hits["5"] += 1
                if r <= 10:
                    hybrid_hits["10"] += 1
                break

        # rerank 精排 top-30 → top-10
        top30_docs = [chunks[idx] for idx in hyb30]
        rr_order = rerank(questions[i], top30_docs, top_k=10)
        for r, local_idx in enumerate(rr_order, 1):
            if hints[i] in top30_docs[local_idx]:
                if r <= 5:
                    rr_hits["5"] += 1
                if r <= 10:
                    rr_hits["10"] += 1
                break

    print(f"\n{'指标':<12}{'混合检索':>10}{'混合+rerank':>12}")
    print("-" * 36)
    for k in ("5", "10"):
        print(f"Recall@{k:<6}{hybrid_hits[k]/n:>9.1%}{rr_hits[k]/n:>11.1%}")


if __name__ == "__main__":
    main()
