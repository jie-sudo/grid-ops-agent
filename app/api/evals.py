"""评估看板接口：离线评测结果的固化存储与读取。

评测是重离线计算（加载嵌入模型、跑全量语料），不适合每次请求实时重跑。
脚本跑完后用 `python scripts/publish_eval_result.py` 把关键指标落库，
评估看板读最新结果即可。
"""
from __future__ import annotations

from fastapi import APIRouter, Depends

from app.core import auth
from app.core.errors import ApiResponse
from app.data import repository

router = APIRouter()


@router.get("/evals/summary", response_model=ApiResponse)
def summary(_user: dict = Depends(auth.get_current_user)) -> ApiResponse:
    """每个评测套件（retrieval/grading/stress）的最新一次结果汇总。"""
    return ApiResponse(data={"suites": repository.eval_summary()})


@router.get("/evals/runs", response_model=ApiResponse)
def runs(limit: int = 20, user: dict = Depends(auth.require_role("admin"))) -> ApiResponse:
    """历史评测运行列表（按时间倒序）。"""
    rows = repository.list_eval_runs(limit)
    return ApiResponse(data={"runs": rows, "count": len(rows)})
