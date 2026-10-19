"""嵌入模型多候选评测（SDD 5.5）：Recall@k / MRR / 命中率 + 逐项耗时。

评测集为自然语言问答对（eval_set.py），替代早期"标题对标题"的低区分度做法。
用法（在 grid-ops-agent 目录下，需 chromadb 运行 + 已装 sentence-transformers）：
    python eval/embedding/benchmark.py
"""
from __future__ import annotations

import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from app.config import get_settings
from app.data.kb import chunk_text, parse_doc
from eval.embedding.eval_set import EVAL_SET

DOCS_DIR = Path(__file__).resolve().parent.parent.parent / "data" / "docs"

CANDIDATES = [
    "BAAI/bge-small-zh-v1.5",
    "BAAI/bge-large-zh-v1.5",
    "BAAI/bge-m3",
    "moka-ai/m3e-base",
]


def load_corpus() -> tuple[list[str], list[str], list[dict]]:
    ids, docs, metas = [], [], []
    for path in sorted(DOCS_DIR.glob("*.md")):
        fm, title, body = parse_doc(path)
        for i, ch in enumerate(chunk_text(body)):
            ids.append(f"{path.stem}-{i}")
            docs.append(ch)
            metas.append({"title": title, "source": fm.get("version", "")})
    return ids, docs, metas


def benchmark_model(model_name: str, eval_set: list[tuple[str, str]], ids, docs, metas) -> dict:
    import chromadb
    from chromadb.config import Settings
    from chromadb.utils import embedding_functions

    s = get_settings()
    ef = embedding_functions.SentenceTransformerEmbeddingFunction(model_name=model_name)
    client = chromadb.HttpClient(host=s.chroma_host, port=s.chroma_port, settings=Settings(anonymized_telemetry=False))
    col = "eval_" + model_name.replace("/", "_").replace("-", "_").replace(".", "_")
    try:
        client.delete_collection(col)
    except Exception:
        pass
    collection = client.get_or_create_collection(col, embedding_function=ef)

    t0 = time.time()
    collection.add(ids=ids, documents=docs, metadatas=metas)
    ingest_time = time.time() - t0

    recall5 = recall10 = hit = mrr = 0.0
    query_times = []
    n = len(eval_set)
    for query, gt in eval_set:
        t = time.time()
        res = collection.query(query_texts=[query], n_results=10, include=["metadatas"])
        query_times.append(time.time() - t)
        titles = [m.get("title", "") for m in res["metadatas"][0]]
        if gt in titles:
            hit += 1
            rank = titles.index(gt) + 1
            mrr += 1.0 / rank
            if rank <= 5:
                recall5 += 1
            if rank <= 10:
                recall10 += 1

    return {
        "model": model_name,
        "recall@5": round(recall5 / n, 4),
        "recall@10": round(recall10 / n, 4),
        "mrr": round(mrr / n, 4),
        "hit@10": round(hit / n, 4),
        "ingest_time_s": round(ingest_time, 2),
        "avg_query_ms": round(sum(query_times) / n * 1000, 1),
    }


def main() -> None:
    ids, docs, metas = load_corpus()
    print(f"评测集 {len(EVAL_SET)} 条（自然语言问答对），语料 {len(docs)} 个片段\n")
    rows = []
    for m in CANDIDATES:
        print(f"评测 {m} ...")
        rows.append(benchmark_model(m, EVAL_SET, ids, docs, metas))

    header = f"{'模型':<28}{'Recall@5':>10}{'Recall@10':>11}{'MRR':>8}{'Hit@10':>9}{'入库耗时':>10}{'均查询ms':>10}"
    print("\n" + header)
    print("-" * len(header))
    for r in rows:
        print(f"{r['model']:<28}{r['recall@5']:>10}{r['recall@10']:>11}{r['mrr']:>8}{r['hit@10']:>9}{r['ingest_time_s']:>9.1f}s{r['avg_query_ms']:>9.1f}")


if __name__ == "__main__":
    main()
