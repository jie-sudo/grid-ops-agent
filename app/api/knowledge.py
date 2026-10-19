"""知识检索接口。"""
from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, Depends

from app.core import auth
from app.core.errors import ApiResponse
from app.data.kb import parse_doc
from app.skills import rag

router = APIRouter()

_DOCS_DIR = Path(__file__).resolve().parents[2] / "data" / "docs"


@router.get("/knowledge/docs", response_model=ApiResponse)
def list_docs(_user: dict = Depends(auth.get_current_user)) -> ApiResponse:
    """知识库文档列表（含版本状态）。"""
    docs = []
    for path in sorted(_DOCS_DIR.glob("*.md")):
        fm, title, _ = parse_doc(path)
        docs.append({
            "title": title,
            "source": fm.get("version", ""),
            "status": fm.get("status", "active"),
            "superseded_by": fm.get("superseded_by", ""),
        })
    return ApiResponse(data={"docs": docs, "count": len(docs)})


@router.post("/knowledge/ingest", response_model=ApiResponse)
def ingest(user: dict = Depends(auth.require_role("admin"))) -> ApiResponse:
    """触发重新入库（幂等 + 版本仲裁）。加完 .md 文档后调用。"""
    from app.data.ingest import ingest_knowledge

    return ApiResponse(data=ingest_knowledge())


@router.get("/knowledge/search", response_model=ApiResponse)
def search(question: str, top_k: int = 5, device_domain: str | None = None) -> ApiResponse:
    return ApiResponse(data=rag.retrieve_knowledge(question, top_k, device_domain))
