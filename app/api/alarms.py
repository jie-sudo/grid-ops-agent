"""告警查询 / 等级判定接口。"""
from __future__ import annotations

from fastapi import APIRouter
from pydantic import BaseModel

from app.core.errors import ApiResponse
from app.skills import alarm

router = APIRouter()


class AlarmAnalyzeReq(BaseModel):
    alarm_type: str
    over_ratio: float = 0.0


@router.get("/alarms", response_model=ApiResponse)
def list_alarms(device_id: str | None = None, hours: int = 24) -> ApiResponse:
    return ApiResponse(data=alarm.query_alarms(device_id, hours))


@router.post("/alarms/analyze", response_model=ApiResponse)
def analyze_alarm(req: AlarmAnalyzeReq) -> ApiResponse:
    return ApiResponse(data=alarm.alarm_level(req.alarm_type, req.over_ratio))
