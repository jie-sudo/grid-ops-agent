"""嵌入模型对比评测：多个中文嵌入模型跑同一套问答集，对比 Recall@K。

用法（SAM2 环境，需 sentence-transformers，模型首次下载走 HF 镜像）：
    python scripts/eval_embedding_models.py                       # 默认 small + base
    python scripts/eval_embedding_models.py --models BAAI/bge-small-zh-v1.5,BAAI/bge-base-zh-v1.5,BAAI/bge-large-zh-v1.5

输出：每个模型的「纯向量」与「混合」Recall@1/@5/@10 对比表。
注意：模型越大越慢，CPU 上 base/large 可能要几分钟~十几分钟，bge-m3 更慢，建议先跑 small+base 看趋势。
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.data.kb import chunk_structured
from app.data.ocr_clean import clean_ocr_text
from app.data.retrieval import keyword_rank, rrf_fuse

MATERIAL_DIR = Path(__file__).resolve().parents[2] / "资料"
OCR_DIR = MATERIAL_DIR / "ocr_text"

DEFAULT_MODELS = [
    "BAAI/bge-small-zh-v1.5",  # 当前基线
    "BAAI/bge-base-zh-v1.5",   # 更大一档
]


def collect() -> list[tuple[str, str]]:
    sources = []
    if OCR_DIR.exists():
        for p in sorted(OCR_DIR.glob("*.txt")):
            if not p.stem.endswith((" (1)", " (2)")):
                sources.append((p.stem, p.read_text(encoding="utf-8")))
    return sources


def evaluate(model, chunks, questions, hints):
    from sentence_transformers import SentenceTransformer

    print(f"  -> 加载 {model} ...")
    m = SentenceTransformer(model)
    chunk_embs = m.encode(chunks, normalize_embeddings=True, show_progress_bar=True)
    q_embs = m.encode(questions, normalize_embeddings=True)

    import numpy as np

    sims = q_embs @ chunk_embs.T
    vec_hits = {"1": 0, "5": 0, "10": 0}
    hyb_hits = {"1": 0, "5": 0, "10": 0}
    for i in range(len(questions)):
        vec_order = list(np.argsort(-sims[i]))
        key_order = keyword_rank(questions[i], chunks, top_k=200)
        hyb_order = rrf_fuse([vec_order[:200], key_order])[:10]

        vr = hr = None
        for r, idx in enumerate(vec_order[:10], 1):
            if hints[i] in chunks[idx]:
                vr = r
                break
        for r, idx in enumerate(hyb_order, 1):
            if hints[i] in chunks[idx]:
                hr = r
                break
        for k in (1, 5, 10):
            if vr and vr <= k:
                vec_hits[str(k)] += 1
            if hr and hr <= k:
                hyb_hits[str(k)] += 1
    return vec_hits, hyb_hits


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--models", default=",".join(DEFAULT_MODELS))
    args = ap.parse_args()
    models = [x.strip() for x in args.models.split(",") if x.strip()]

    from eval.qa_set import QA_SET

    chunks: list[str] = []
    for stem, raw in collect():
        clean = clean_ocr_text(raw)
        if clean.strip():
            chunks.extend(chunk_structured(clean))
    questions = [qa["q"] for qa in QA_SET]
    hints = [qa["hint"] for qa in QA_SET]
    n = len(QA_SET)
    print(f"共 {len(chunks)} chunk，{n} 个问题\n")

    print(f"{'模型':<40}{'向量R@5':>10}{'混合R@5':>10}{'混合R@10':>10}")
    print("-" * 72)
    for model in models:
        vec, hyb = evaluate(model, chunks, questions, hints)
        print(f"{model:<40}{vec['5']/n:>9.1%}{hyb['5']/n:>9.1%}{hyb['10']/n:>9.1%}")


if __name__ == "__main__":
    main()
