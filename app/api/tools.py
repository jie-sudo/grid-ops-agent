"""工具注册表接口。"""
from __future__ import annotations

from fastapi import APIRouter, Depends

from app.core import auth
from app.core.errors import ApiResponse
from app.engine.tools import list_tools
from app.tools import register_all_tools

router = APIRouter()


@router.get("/tools", response_model=ApiResponse)
def get_tools(_user: dict = Depends(auth.get_current_user)) -> ApiResponse:
    register_all_tools()
    tools = [
        {"name": t.name, "description": t.description, "params": t.params_schema, "read_only": t.read_only}
        for t in list_tools()
    ]
    return ApiResponse(data={"tools": tools, "count": len(tools)})
