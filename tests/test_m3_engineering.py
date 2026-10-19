"""工程化加固验收：RAG 版本治理（纯逻辑，不需 DB/ChromaDB）。"""
from pathlib import Path

from app.data.kb import chunk_text, parse_doc
from app.data.vectorstore import build_filter

DOCS = Path(__file__).resolve().parent.parent / "data" / "docs"


def test_parse_superseded_doc():
    """已废止示例文档的 front matter 应带 status=superseded。"""
    doc4 = DOCS / "04-危急缺陷消缺时限（历史版本示例，已废止）.md"
    fm, _, _ = parse_doc(doc4)
    assert fm["status"] == "superseded"


def test_chunk_text():
    chunks = chunk_text("第一段。\n\n" + "第二段内容。\n" * 50)
    assert len(chunks) >= 1
    assert all(len(c) > 0 for c in chunks)


def test_build_filter_excludes_superseded():
    w = build_filter({"device_domain": "变压器"}, exclude_superseded=True)
    assert "$and" in w
    assert {"status": {"$ne": "superseded"}} in w["$and"]


def test_build_filter_no_exclude():
    assert build_filter({"device_domain": "变压器"}, exclude_superseded=False) == {"device_domain": "变压器"}
    assert build_filter(None, exclude_superseded=False) is None
