"""缺陷分级 / 时限 / 列表接口。"""
from __future__ import annotations

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from app.core import auth
from app.core.errors import ApiResponse
from app.data import repository
from app.skills import defect

router = APIRouter()


class DefectEvalReq(BaseModel):
    description: str


@router.get("/defects", response_model=ApiResponse)
def list_defects(
    level: str | None = None,
    device_id: str | None = None,
    start: str | None = None,
    end: str | None = None,
    limit: int = 50,
    offset: int = 0,
    _user: dict = Depends(auth.get_current_user),
) -> ApiResponse:
    defects = repository.list_defects(level, device_id, start, end, limit, offset)
    return ApiResponse(data={"defects": defects, "count": len(defects)})


@router.post("/defects/evaluate", response_model=ApiResponse)
def evaluate(req: DefectEvalReq) -> ApiResponse:
    return ApiResponse(data=defect.grade_defect(req.description))


@router.get("/defects/deadline/{level}", response_model=ApiResponse)
def deadline(level: str) -> ApiResponse:
    return ApiResponse(data=defect.deadline_for(level))
