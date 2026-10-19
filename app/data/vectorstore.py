"""向量库抽象：ChromaDB（默认），嵌入函数可插拔（SDD 5.5 多候选评测）。

版本治理：检索默认排除 status=superseded 的旧版语料（SDD 5.3）。
"""
from __future__ import annotations

from typing import Any


def build_filter(where: dict | None, exclude_superseded: bool = True) -> dict | None:
    """构造 ChromaDB where 过滤；默认排除 status=superseded 的旧版语料。"""
    if exclude_superseded:
        status_filter = {"status": {"$ne": "superseded"}}
        return {"$and": [where, status_filter]} if where else status_filter
    return where


def _resolve_embedding_function(embedding_function: Any) -> Any:
    """未显式指定时按配置选：embedding_model 为空用 chromadb 默认（英文 miniLM），否则用本地中文模型。"""
    if embedding_function is not None:
        return embedding_function
    from app.config import get_settings

    model = get_settings().embedding_model
    if not model:
        return None
    from chromadb.utils import embedding_functions

    return embedding_functions.SentenceTransformerEmbeddingFunction(model_name=model)


class VectorStore:
    def __init__(
        self,
        host: str = "localhost",
        port: int = 8000,
        collection_name: str = "knowledge",
        embedding_function: Any = None,
    ) -> None:
        import chromadb
        from chromadb.config import Settings

        self.client = chromadb.HttpClient(
            host=host,
            port=port,
            settings=Settings(anonymized_telemetry=False),
        )
        self.collection = self.client.get_or_create_collection(
            name=collection_name,
            embedding_function=_resolve_embedding_function(embedding_function),
        )

    def add(self, ids: list[str], documents: list[str], metadatas: list[dict]) -> None:
        self.collection.add(ids=ids, documents=documents, metadatas=metadatas)

    def search(
        self,
        query: str,
        top_k: int = 5,
        where: dict | None = None,
        exclude_superseded: bool = True,
    ) -> list[dict]:
        res = self.collection.query(
            query_texts=[query],
            n_results=top_k,
            where=build_filter(where, exclude_superseded),
            include=["documents", "metadatas", "distances"],
        )
        docs = res.get("documents", [[]])[0]
        metas = res.get("metadatas", [[]])[0]
        return [self._build_chunk(docs[i], metas[i]) for i in range(len(docs))]

    @staticmethod
    def _build_chunk(doc: str, meta: dict | None) -> dict:
        meta = meta or {}
        return {
            "content": doc,
            "source": meta.get("source", ""),
            "title": meta.get("title", ""),
            "device_domain": meta.get("device_domain", ""),
            "status": meta.get("status", "active"),
        }

    def _all(self, where: dict | None = None, exclude_superseded: bool = True):
        """取全部 chunk（含过滤），供关键词检索。"""
        res = self.collection.get(
            where=build_filter(where, exclude_superseded),
            include=["documents", "metadatas"],
        )
        return res.get("documents", []), res.get("metadatas", [])

    def hybrid_search(
        self,
        query: str,
        top_k: int = 5,
        where: dict | None = None,
        exclude_superseded: bool = True,
    ) -> list[dict]:
        """混合检索：向量 + 关键词，RRF 融合。"""
        from app.data.retrieval import keyword_rank, rrf_fuse

        docs, metas = self._all(where, exclude_superseded)
        if not docs:
            return []
        # 向量路
        vec = self.search(query, top_k=top_k * 4, where=where, exclude_superseded=exclude_superseded)
        idx_by_content = {d: i for i, d in enumerate(docs)}
        vec_idx = [idx_by_content[c["content"]] for c in vec if c["content"] in idx_by_content]
        # 关键词路
        key_idx = keyword_rank(query, docs, top_k=top_k * 4)
        # RRF 融合（关键词路权重更高：精确字面匹配优先，避免被向量语义噪声淹没）
        fused = rrf_fuse([vec_idx, key_idx], weights=[1.0, 2.0])[:top_k]
        return [self._build_chunk(docs[i], metas[i]) for i in fused]
