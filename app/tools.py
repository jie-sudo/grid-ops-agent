"""工具注册入口：把各业务能力封装为可被调度器调用的工具（M4 使用）。"""
from __future__ import annotations

from app.engine.tools import Tool, register
from app.data import repository
from app.skills import alarm, defect, diagnosis, query, rag, review_case, workorder


def register_all_tools() -> None:
    register(Tool(
        name="retrieve_knowledge",
        description="检索知识库，返回带出处的文档片段（规程/处置卡/标准）",
        params_schema={"question": "str", "top_k": "int=5", "device_domain": "str=None"},
        handler=rag.retrieve_knowledge,
    ))
    register(Tool(
        name="query_device",
        description="按设备编号查询台账",
        params_schema={"device_id": "str"},
        handler=query.query_device,
    ))
    register(Tool(
        name="query_measurements",
        description="查询设备量测时序（实时 + 历史）",
        params_schema={"device_id": "str", "measure_type": "str=None", "hours": "int=24"},
        handler=query.query_measurements,
    ))
    register(Tool(
        name="query_state",
        description="设备状态四态评价（正常/注意/异常/严重）",
        params_schema={"device_id": "str"},
        handler=query.query_state,
    ))
    register(Tool(
        name="query_alarms",
        description="查询设备告警列表",
        params_schema={"device_id": "str=None", "hours": "int=24"},
        handler=alarm.query_alarms,
    ))
    register(Tool(
        name="alarm_level",
        description="告警等级判定（提示/重要/紧急）",
        params_schema={"alarm_type": "str", "over_ratio": "float=0.0"},
        handler=alarm.alarm_level,
    ))
    register(Tool(
        name="grade_defect",
        description="缺陷等级判定（一般/严重/危急）",
        params_schema={"description": "str", "device_type": "str=None"},
        handler=defect.grade_defect,
    ))
    register(Tool(
        name="diagnose",
        description="设备故障诊断（确定性规则）",
        params_schema={"device_type": "str", "measurements": "dict"},
        handler=diagnosis.diagnose,
    ))
    register(Tool(
        name="create_workorder_draft",
        description="生成工单草稿（待二次确认）",
        params_schema={"defect_level": "str", "content": "str", "device_id": "str=None", "assignee": "str=None"},
        handler=workorder.create_workorder_draft,
    ))
    register(Tool(
        name="deadline_for",
        description="缺陷等级 → 消缺时限",
        params_schema={"level": "str"},
        handler=defect.deadline_for,
    ))
    register(Tool(
        name="create_work_order",
        description="工单落库（写操作，须二次确认后调用；idempotency_key 防重复落库）",
        params_schema={"order": "dict", "idempotency_key": "str=None"},
        handler=repository.create_work_order,
        read_only=False,
    ))
    register(Tool(
        name="search_review_cases",
        description="检索已审核且未废止的历史处置案例（现象/根因/处置），供诊断参考",
        params_schema={"query": "str", "device_type": "str=None", "limit": "int=8"},
        handler=review_case.search_review_cases,
    ))
