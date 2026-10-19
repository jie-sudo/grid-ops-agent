"""设备台账 / 量测 / 状态查询接口。"""
from __future__ import annotations

from fastapi import APIRouter, Depends

from app.core import auth
from app.core.errors import ApiResponse
from app.data import repository
from app.skills import query

router = APIRouter()


@router.get("/devices", response_model=ApiResponse)
def list_devices(keyword: str | None = None, limit: int = 50, _user: dict = Depends(auth.get_current_user)) -> ApiResponse:
    """设备列表 + 模糊搜索（供前端选择器）。"""
    devices = repository.list_devices(keyword, limit)
    return ApiResponse(data={"devices": devices, "count": len(devices)})


@router.get("/devices/{device_id}", response_model=ApiResponse)
def get_device(device_id: str) -> ApiResponse:
    return ApiResponse(data=query.query_device(device_id))


@router.get("/devices/{device_id}/overview", response_model=ApiResponse)
def overview(device_id: str, _user: dict = Depends(auth.get_current_user)) -> ApiResponse:
    """设备实时状态聚合：台账 + 四态 + 最新量测 + 最近告警（供前端轮询）。"""
    from app.data.realtime import get_source

    device = repository.get_device(device_id)
    if device is None:
        return ApiResponse(data={"found": False, "message": f"设备 {device_id} 不存在"})
    state = query.query_state(device_id)
    measurements = get_source().get_latest(device_id)
    alarms = repository.query_alarms(device_id, hours=1)
    return ApiResponse(data={
        "found": True,
        "device": device,
        "state": state,
        "measurements": measurements,
        "alarms": alarms,
        "alarm_count": len(alarms),
    })


@router.get("/devices/{device_id}/measurements", response_model=ApiResponse)
def get_measurements(device_id: str, measure_type: str | None = None, hours: int = 24) -> ApiResponse:
    return ApiResponse(data=query.query_measurements(device_id, measure_type, hours))


@router.get("/devices/{device_id}/state", response_model=ApiResponse)
def get_state(device_id: str) -> ApiResponse:
    return ApiResponse(data=query.query_state(device_id))
