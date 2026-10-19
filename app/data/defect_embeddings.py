"""缺陷库嵌入匹配（探索，当前未启用）。

⚠️ 经验证不适用缺陷定级场景：压测 500 样本，bigram 字面匹配命中率 71%、误判 0，
嵌入语义匹配命中率仅 2%（语义相似度把"绝缘电阻不合格"vs"电容量不合格"等细微差异抹平，
导致跨等级歧义降级）。电力缺陷是规范化术语，字面即标准，精确匹配优先。

保留本模块供未来"口语化输入归一化"探索：用户用口语描述缺陷（"这变压器好像漏油了"）时，
可先用嵌入/LLM 归一化到规范术语，再走 bigram 定级——那是"输入归一化"层，不是"定级匹配"层。
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

import numpy as np

RULES_DIR = Path(__file__).resolve().parents[2] / "rules"
CACHE = RULES_DIR / ".defect_embeddings.npz"
MODEL_NAME = "BAAI/bge-small-zh-v1.5"

_model = None


def _get_model():
    global _model
    if _model is None:
        from sentence_transformers import SentenceTransformer

        _model = SentenceTransformer(MODEL_NAME)
    return _model


def _hay(rec: dict) -> str:
    # 只取"缺陷描述 + 分类依据"做语义匹配；设备字段（device_type/component）用 device_type 过滤处理，
    # 不混进嵌入文本，否则会稀释 query 与记录的语义相似度
    return " ".join(x for x in [rec.get("defect", ""), rec.get("basis", "")] if x).strip()


def _fingerprint(records: list[dict]) -> str:
    return hashlib.md5(
        json.dumps(records, ensure_ascii=False, sort_keys=True).encode("utf-8")
    ).hexdigest()


def _load_or_build(records: list[dict]):
    """加载预嵌入缓存；缺陷库内容变了就重建。"""
    fp = _fingerprint(records)
    if CACHE.exists():
        try:
            data = np.load(CACHE, allow_pickle=True)
            if str(data["fingerprint"]) == fp:
                return data["vectors"]
        except Exception:
            pass
    vectors = _get_model().encode([_hay(r) for r in records], normalize_embeddings=True)
    np.savez(CACHE, vectors=vectors, fingerprint=np.array(fp))
    return vectors


def match_by_embedding(query: str, records: list[dict], device_type: str | None = None, threshold: float = 0.6):
    """嵌入相似度匹配，返回 (level, record) 或 (None, None)。

    沿用安全约束：仅单一等级命中才定级；设备类型过滤同 bigram 版。
    """
    if not records:
        return None, None
    if device_type:
        filtered = [r for r in records if device_type in (
            (r.get("device_type") or "") + (r.get("device_category") or "")
            + (r.get("device_kind") or "") + (r.get("component") or "")
        )]
        if filtered:
            records = filtered
    vectors = _load_or_build(records)
    q = _get_model().encode([query], normalize_embeddings=True)[0]
    sims = vectors @ q
    matched_levels: set[str] = set()
    best = None
    best_score = -1.0
    for i, rec in enumerate(records):
        if sims[i] >= threshold:
            matched_levels.add(rec.get("level"))
            if sims[i] > best_score:
                best_score, best = sims[i], rec
    if len(matched_levels) == 1 and best is not None:
        return best.get("level"), best
    return None, None
