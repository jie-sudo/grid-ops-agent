"""工单接口：草稿生成 / 落库草稿 / 确认 / 取消 / 列表。"""
from __future__ import annotations

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from app.core import auth
from app.core.errors import ApiResponse
from app.data import repository
from app.skills import workorder

router = APIRouter()


class DraftReq(BaseModel):
    defect_level: str
    content: str
    device_id: str | None = None
    assignee: str | None = None


class OrderReq(BaseModel):
    """落库草稿请求：消缺时限由后端按等级规则计算（可覆盖）。"""

    ref_type: str = "缺陷"
    ref_id: str | None = None
    content: str
    level: str
    deadline: str | None = None  # ISO 字符串；空则由等级规则补齐
    assignee: str | None = None


@router.get("/workorders", response_model=ApiResponse)
def list_work_orders(
    level: str | None = None,
    device_id: str | None = None,
    start: str | None = None,
    end: str | None = None,
    limit: int = 50,
    offset: int = 0,
    _user: dict = Depends(auth.get_current_user),
) -> ApiResponse:
    orders = repository.list_work_orders(level, device_id, start, end, limit, offset)
    return ApiResponse(data={"workorders": orders, "count": len(orders)})


@router.post("/workorders/draft", response_model=ApiResponse)
def draft(req: DraftReq) -> ApiResponse:
    return ApiResponse(data=workorder.create_workorder_draft(
        req.defect_level, req.content, req.device_id, req.assignee
    ))


@router.post("/workorders", response_model=ApiResponse)
def create_draft(req: OrderReq, _user: dict = Depends(auth.get_current_user)) -> ApiResponse:
    """落库工单草稿（status=草稿），返回 order_id 供后续确认/取消。"""
    draft = workorder.create_workorder_draft(req.level, req.content, req.ref_id, req.assignee)["draft"]
    draft["ref_type"] = req.ref_type
    if req.deadline:
        draft["deadline"] = req.deadline
    return ApiResponse(data=repository.create_workorder_draft_record(draft))


@router.post("/workorders/{order_id}/confirm", response_model=ApiResponse)
def confirm(order_id: str, user: dict = Depends(auth.require_role("manager", "admin"))) -> ApiResponse:
    return ApiResponse(data=repository.confirm_work_order(order_id, user["user_id"]))


@router.post("/workorders/{order_id}/cancel", response_model=ApiResponse)
def cancel(order_id: str, user: dict = Depends(auth.require_role("manager", "admin"))) -> ApiResponse:
    return ApiResponse(data=repository.cancel_work_order(order_id))
