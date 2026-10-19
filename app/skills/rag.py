"""RAG 检索能力（FR-010/011）。"""
from __future__ import annotations

from app.config import get_settings
from app.data.vectorstore import VectorStore

_store: VectorStore | None = None


def _get_store() -> VectorStore:
    global _store
    if _store is None:
        s = get_settings()
        _store = VectorStore(host=s.chroma_host, port=s.chroma_port)
    return _store


def retrieve_knowledge(question: str, top_k: int = 5, device_domain: str | None = None, exclude_superseded: bool = True, use_rerank: bool = True) -> dict:
    """混合检索 + 精排，返回带出处的候选片段；默认排除 superseded 语料，无结果返回空列表（不编造）。

    use_rerank：召回 top_k*6 后用交叉编码器精排取 top_k（更准，慢约几百毫秒）。
    """
    store = _get_store()
    where = {"device_domain": device_domain} if device_domain else None
    # 召回 top_k*6，供 rerank 精排后取 top_k
    recall_k = top_k * 6 if use_rerank else top_k
    chunks = store.hybrid_search(question, top_k=recall_k, where=where, exclude_superseded=exclude_superseded)
    if use_rerank and len(chunks) > top_k:
        from app.data.rerank import rerank

        order = rerank(question, [c["content"] for c in chunks], top_k=top_k)
        chunks = [chunks[i] for i in order]
    return {"chunks": chunks, "count": len(chunks)}
