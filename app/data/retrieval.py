"""混合检索的纯函数：关键词打分 + RRF 融合（可单测，不依赖 ChromaDB/嵌入）。

思路：向量检索管"语义相近"，关键词检索管"精确词命中"（如"总烃含量""受令人接令后"），
两者用 RRF（倒数排名融合）合并，补纯向量检索在语义竞争下的短板。
"""
from __future__ import annotations

import re


def keyword_terms(query: str) -> set[str]:
    """提取查询的关键词：中文字符 bigram + 含数字的片段。

    中文无分词器时，字符 bigram 是简单有效的关键词近似。
    """
    q = re.sub(r"[^一-鿿0-9A-Za-z]+", "", query or "")
    terms: set[str] = set()
    for i in range(len(q) - 1):
        bg = q[i : i + 2]
        if any("一" <= c <= "鿿" for c in bg) or any(c.isdigit() for c in bg):
            terms.add(bg)
    return terms


def keyword_score(query: str, doc: str) -> float:
    """查询与文档的关键词重叠度（0~1）。"""
    terms = keyword_terms(query)
    if not terms:
        return 0.0
    return sum(1 for t in terms if t in doc) / len(terms)


def keyword_rank(query: str, docs: list[str], top_k: int = 10) -> list[int]:
    """按关键词分降序返回文档下标（只含分数 >0 的）。"""
    scored = [(i, keyword_score(query, d)) for i, d in enumerate(docs)]
    scored = [(i, s) for i, s in scored if s > 0]
    scored.sort(key=lambda x: -x[1])
    return [i for i, _ in scored[:top_k]]


def rrf_fuse(ranked_lists: list[list[int]], k: int = 60, weights: list[float] | None = None) -> list[int]:
    """RRF（倒数排名融合）合并多路排序，返回融合后的下标序。

    weights：各路权重（通用超参，默认等权）。精确匹配路（如关键词）可给更高权重，
    避免被语义相似路的噪声淹没。
    """
    if weights is None:
        weights = [1.0] * len(ranked_lists)
    scores: dict[int, float] = {}
    for lst, w in zip(ranked_lists, weights):
        for rank, idx in enumerate(lst):
            scores[idx] = scores.get(idx, 0) + w / (k + rank + 1)
    return [i for i, _ in sorted(scores.items(), key=lambda x: -x[1])]
