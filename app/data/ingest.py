"""知识库入库：幂等（删旧重加）+ 版本仲裁（同源多版本自动 supersede）。

被 scripts/ingest_kb.py 和 POST /knowledge/ingest 接口共同调用。
"""
from __future__ import annotations

from pathlib import Path

from app.config import get_settings
from app.data.kb import chunk_text, infer_domain, parse_doc
from app.data.vectorstore import VectorStore

DOCS_DIR = Path(__file__).resolve().parents[2] / "data" / "docs"


def arbitrate_versions(docs: list[dict]) -> list[dict]:
    """版本仲裁（纯函数，可单测）：同 source（标准号）多版本 → effective_date 最新的 active，其余 superseded。

    输入 docs 列表，每项含 fm(version/status/effective_date)、title 等；
    就地设置 final_status / superseded_by，返回被废止的 title 列表。
    """
    superseded_titles: list[str] = []
    by_source: dict[str, list[dict]] = {}
    for d in docs:
        src = d["fm"].get("version", "") or d["stem"]
        by_source.setdefault(src, []).append(d)

    for versions in by_source.values():
        if len(versions) > 1:
            versions.sort(key=lambda d: (d["fm"].get("effective_date", "") or ""))
            latest_version = versions[-1]["fm"].get("version", "")
            for v in versions[:-1]:
                v["final_status"] = "superseded"
                v["superseded_by"] = latest_version
                superseded_titles.append(v["title"])
    return superseded_titles


def ingest_knowledge() -> dict:
    """幂等入库 + 版本仲裁。返回 {docs, chunks, active_chunks, superseded_docs}。"""
    settings = get_settings()
    store = VectorStore(host=settings.chroma_host, port=settings.chroma_port)

    docs: list[dict] = []
    for path in sorted(DOCS_DIR.glob("*.md")):
        fm, title, body = parse_doc(path)
        docs.append({"stem": path.stem, "fm": fm, "title": title, "body": body})

    # 版本仲裁：同 source（标准号）多版本 → effective_date 最新的 active，其余 superseded
    superseded_docs = arbitrate_versions(docs)

    total_chunks = 0
    active_chunks = 0
    for d in docs:
        status = d.get("final_status", d["fm"].get("status", "active"))
        # 幂等：先删旧 chunks（按 title），再 add 新的
        try:
            store.collection.delete(where={"title": d["title"]})
        except Exception:
            pass

        ids, chunks, metas = [], [], []
        for i, ch in enumerate(chunk_text(d["body"])):
            ids.append(f"{d['stem']}-{i}")
            chunks.append(ch)
            metas.append({
                "title": d["title"],
                "source": d["fm"].get("version", ""),
                "device_domain": infer_domain(d["title"], d["body"]),
                "status": status,
                "superseded_by": d.get("superseded_by", d["fm"].get("superseded_by", "")),
                "effective_date": d["fm"].get("effective_date", ""),
            })
        if ids:
            store.add(ids, chunks, metas)
            total_chunks += len(ids)
            if status != "superseded":
                active_chunks += len(ids)

    return {
        "docs": len(docs),
        "chunks": total_chunks,
        "active_chunks": active_chunks,
        "superseded_docs": superseded_docs,
    }
