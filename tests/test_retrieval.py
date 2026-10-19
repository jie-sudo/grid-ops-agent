"""混合检索纯函数单测。"""
from app.data.retrieval import keyword_rank, keyword_score, keyword_terms, rrf_fuse


def test_keyword_terms_chinese_bigram():
    terms = keyword_terms("总烃含量大于多少")
    assert "总烃" in terms
    assert "含量" in terms


def test_keyword_score():
    assert keyword_score("总烃含量", "总烃含量大于150μL/L") > 0.5
    assert keyword_score("总烃含量", "绝缘纸聚合度≤250") == 0.0


def test_keyword_rank_rescues_exact_phrase():
    docs = [
        "绝缘纸聚合度≤250",
        "总烃含量大于150μL/L 产气速率大于10%/月",
        "乙炔含量大于注意值",
    ]
    ranked = keyword_rank("总烃含量大于多少", docs, top_k=5)
    assert ranked[0] == 1  # 精确词命中的 chunk 排第一


def test_rrf_fuse_combines_two_lists():
    # 向量 [0,1,2]，关键词 [1,2,3] → 1、2 两路都命中，1 排更靠前
    fused = rrf_fuse([[0, 1, 2], [1, 2, 3]])
    assert fused[0] == 1
    assert set(fused) == {0, 1, 2, 3}
