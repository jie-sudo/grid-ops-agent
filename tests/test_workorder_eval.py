"""工单确认草稿 + 评估结果固化（纯逻辑，不碰 DB）。

repository 的落库/确认函数依赖 PG，这里只测可脱离 DB 验证的部分：
草稿生成规则（deadline 兜底）、请求模型校验、接口/模型可导入、函数签名存在。
"""
from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from app.skills import workorder


def test_create_workorder_draft_status_and_deadline():
    d = workorder.create_workorder_draft("危急", "变压器温度越限", "DEV1")["draft"]
    assert d["status"] == "草稿"
    assert d["level"] == "危急"
    assert d["ref_id"] == "DEV1"
    # 危急 24 小时内消除：deadline 是可解析的 ISO 字符串且在未来
    deadline = datetime.fromisoformat(d["deadline"])
    assert deadline > datetime.now(timezone.utc)


def test_create_workorder_draft_general_level_deadline_not_none():
    # 一般缺陷无硬性时限（列入年/季计划），兜底 90 天，避免落库 NOT NULL 崩溃
    d = workorder.create_workorder_draft("一般", "轻微锈蚀")["draft"]
    assert d["deadline"] is not None
    assert datetime.fromisoformat(d["deadline"]) > datetime.now(timezone.utc)


def test_create_workorder_draft_deadline_ordered_by_level():
    urgent = datetime.fromisoformat(workorder.create_workorder_draft("危急", "x")["draft"]["deadline"])
    severe = datetime.fromisoformat(workorder.create_workorder_draft("严重", "x")["draft"]["deadline"])
    assert urgent < severe  # 危急（24h）比严重（30d）更早


def test_order_req_defaults():
    from app.api.workorders import OrderReq

    req = OrderReq(content="x", level="严重")
    assert req.ref_type == "缺陷"
    assert req.ref_id is None
    assert req.deadline is None


def test_order_req_requires_content_and_level():
    from app.api.workorders import OrderReq

    with pytest.raises(ValidationError):
        OrderReq(level="严重")  # 缺 content
    with pytest.raises(ValidationError):
        OrderReq(content="x")  # 缺 level


def test_workorder_and_eval_repository_importable():
    from app.data import repository

    for fn in (
        "create_workorder_draft_record",
        "confirm_work_order",
        "cancel_work_order",
        "save_eval_run",
        "list_eval_runs",
        "eval_summary",
    ):
        assert callable(getattr(repository, fn))


def test_eval_run_model_importable():
    from app.data.models import EvalRun

    assert EvalRun.__tablename__ == "eval_run"


def test_evals_api_importable():
    from app.api import evals

    paths = [r.path for r in evals.router.routes]
    assert "/evals/summary" in paths
    assert "/evals/runs" in paths
