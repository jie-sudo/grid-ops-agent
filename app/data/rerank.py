"""Rerank 精排：交叉编码器对召回候选重排（懒加载，进程内单例缓存）。

交叉编码器把 query 和候选成对输入算相关性，比双编码器的余弦相似度更准，
但更慢，所以只对粗排召回的前 K 个做精排。
"""
from __future__ import annotations

_reranker = None
_model_name = None


def get_reranker(model_name: str = "BAAI/bge-reranker-base"):
    global _reranker, _model_name
    if _reranker is None or _model_name != model_name:
        from sentence_transformers import CrossEncoder

        _reranker = CrossEncoder(model_name, max_length=512)
        _model_name = model_name
    return _reranker


def rerank(query: str, docs: list[str], top_k: int = 5, model_name: str = "BAAI/bge-reranker-base", keyword_weight: float = 0.5) -> list[int]:
    """对 docs 精排，返回按相关性降序的 top_k 下标。

    交叉编码器分数（sigmoid 归一化到 0~1）+ keyword_weight × 关键词命中分数（0~1）。
    关键词项是通用保护：避免交叉编码器对"精确字面匹配"的判断偏差把对的排下去。
    """
    if not docs:
        return []
    import numpy as np

    from app.data.retrieval import keyword_score

    model = get_reranker(model_name)
    logits = model.predict([(query, d) for d in docs])
    probs = 1.0 / (1.0 + np.exp(-np.array(logits, dtype=float)))
    key_scores = np.array([keyword_score(query, d) for d in docs], dtype=float)
    final = probs + keyword_weight * key_scores
    order = sorted(range(len(docs)), key=lambda i: -final[i])
    return order[:top_k]
