"""故障诊断接口。"""
from __future__ import annotations

from fastapi import APIRouter
from pydantic import BaseModel

from app.core.errors import ApiResponse
from app.skills import diagnosis

router = APIRouter()


class DiagnoseReq(BaseModel):
    device_type: str
    measurements: dict


@router.post("/diagnoses", response_model=ApiResponse)
def diagnose(req: DiagnoseReq) -> ApiResponse:
    return ApiResponse(data=diagnosis.diagnose(req.device_type, req.measurements))
