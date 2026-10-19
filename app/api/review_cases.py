"""复盘案例接口：列表 / 检索 / 审核（审核限 manager/admin）。"""
from __future__ import annotations

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from app.core import auth
from app.core.errors import ApiResponse
from app.data import repository

router = APIRouter()


class SupersedeReq(BaseModel):
    new_case_id: str | None = None


@router.get("/review-cases", response_model=ApiResponse)
def list_review_cases(
    status: str | None = None,
    device_type: str | None = None,
    limit: int = 50,
    offset: int = 0,
    _user: dict = Depends(auth.get_current_user),
) -> ApiResponse:
    cases = repository.list_review_cases(status, device_type, limit, offset)
    return ApiResponse(data={"cases": cases, "count": len(cases)})


@router.get("/review-cases/search", response_model=ApiResponse)
def search_review_cases(
    q: str,
    device_type: str | None = None,
    _user: dict = Depends(auth.get_current_user),
) -> ApiResponse:
    return ApiResponse(data={"cases": repository.search_review_cases(q, device_type)})


@router.post("/review-cases/{case_id}/approve", response_model=ApiResponse)
def approve(case_id: str, user: dict = Depends(auth.require_role("manager", "admin"))) -> ApiResponse:
    return ApiResponse(data=repository.approve_review_case(case_id, user["user_id"]))


@router.post("/review-cases/{case_id}/reject", response_model=ApiResponse)
def reject(case_id: str, user: dict = Depends(auth.require_role("manager", "admin"))) -> ApiResponse:
    return ApiResponse(data=repository.reject_review_case(case_id, user["user_id"]))


@router.post("/review-cases/{case_id}/supersede", response_model=ApiResponse)
def supersede(
    case_id: str,
    req: SupersedeReq,
    user: dict = Depends(auth.require_role("manager", "admin")),
) -> ApiResponse:
    return ApiResponse(data=repository.supersede_review_case(case_id, req.new_case_id, user["user_id"]))
