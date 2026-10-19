"""数据访问仓储：查询走只读连接，写操作走读写连接（工程化只读保护）。"""
from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import func

from app.data import models
from app.data.database import get_read_session, get_write_session


def _parse_dt(value):
    """把 ISO 字符串 / datetime 转成 datetime；非法输入返回 None。"""
    if value is None:
        return None
    if isinstance(value, datetime):
        return value
    try:
        return datetime.fromisoformat(str(value))
    except (ValueError, TypeError):
        return None


def get_device(device_id: str) -> dict | None:
    with get_read_session() as s:
        d = s.get(models.Device, device_id)
        if d is None:
            return None
        return {
            "device_id": d.device_id,
            "device_name": d.device_name,
            "device_type": d.device_type,
            "voltage_level": d.voltage_level,
            "station": d.station,
            "status": d.status,
        }


def get_latest_value(device_id: str, measure_type: str) -> float | None:
    with get_read_session() as s:
        row = (
            s.query(models.MeasurePoint)
            .filter_by(device_id=device_id, measure_type=measure_type)
            .first()
        )
        return row.latest_value if row else None


def query_measurements(device_id: str, measure_type: str | None = None, hours: int = 24) -> list[dict]:
    with get_read_session() as s:
        q = s.query(models.MeasurePoint).filter_by(device_id=device_id)
        if measure_type:
            q = q.filter_by(measure_type=measure_type)
        point_ids = [p.point_id for p in q.all()]
        if not point_ids:
            return []
        since = datetime.now(timezone.utc) - timedelta(hours=hours)
        rows = (
            s.query(models.MeasureValue)
            .filter(models.MeasureValue.point_id.in_(point_ids), models.MeasureValue.ts >= since)
            .order_by(models.MeasureValue.ts.desc())
            .limit(1000)
            .all()
        )
        return [
            {"point_id": r.point_id, "ts": r.ts.isoformat(), "value": r.value, "quality": r.quality}
            for r in rows
        ]


def query_alarms(device_id: str | None = None, hours: int = 24) -> list[dict]:
    with get_read_session() as s:
        since = datetime.now(timezone.utc) - timedelta(hours=hours)
        q = s.query(models.Alarm).filter(models.Alarm.trigger_time >= since)
        if device_id:
            q = q.filter_by(device_id=device_id)
        rows = q.order_by(models.Alarm.trigger_time.desc()).limit(200).all()
        return [
            {
                "alarm_id": r.alarm_id,
                "device_id": r.device_id,
                "alarm_type": r.alarm_type,
                "level": r.level,
                "trigger_time": r.trigger_time.isoformat(),
                "status": r.status,
            }
            for r in rows
        ]


def create_work_order(order: dict, idempotency_key: str | None = None) -> dict:
    """落库工单（写路径，调用方须先过二次确认闸口）。

    idempotency_key：幂等键。重复确认/重试时若已存在同键工单则直接返回，
    不重复落库（中断恢复的关键保证，对应 AegisOps 的"未重复创建工单"）。
    """
    with get_write_session() as s:
        if idempotency_key:
            existing = s.query(models.WorkOrder).filter_by(idempotency_key=idempotency_key).first()
            if existing:
                return {"order_id": existing.order_id, "status": existing.status, "duplicate": True}
        data = dict(order)
        data.setdefault("order_id", f"WO{uuid.uuid4().hex[:24]}")
        data["status"] = "已下发"  # 二次确认后落库
        data["confirm_time"] = datetime.now(timezone.utc)
        # 草稿里的 deadline 是 ISO 字符串，转回 datetime
        if isinstance(data.get("deadline"), str):
            data["deadline"] = datetime.fromisoformat(data["deadline"])
        data["idempotency_key"] = idempotency_key
        wo = models.WorkOrder(**data)
        s.add(wo)
        s.commit()
        return {"order_id": wo.order_id, "status": wo.status}


def create_workorder_draft_record(order: dict, idempotency_key: str | None = None) -> dict:
    """落库工单草稿（status=草稿），供前端工单页独立出草稿/确认/取消。

    与 create_work_order（确认后直接落库「已下发」）区分：草稿先落库，可被
    confirm_work_order / cancel_work_order 推进，列表页可见、可断点恢复。
    """
    with get_write_session() as s:
        if idempotency_key:
            existing = s.query(models.WorkOrder).filter_by(idempotency_key=idempotency_key).first()
            if existing:
                return {"order_id": existing.order_id, "status": existing.status, "duplicate": True}
        data = dict(order)
        data["order_id"] = data.get("order_id") or f"WO{uuid.uuid4().hex[:24]}"
        data["status"] = "草稿"
        if isinstance(data.get("deadline"), str):
            data["deadline"] = datetime.fromisoformat(data["deadline"])
        data["idempotency_key"] = idempotency_key
        wo = models.WorkOrder(**data)
        s.add(wo)
        s.commit()
        return {"order_id": wo.order_id, "status": wo.status}


def confirm_work_order(order_id: str, user_id: str | None = None) -> dict:
    """草稿 → 已下发（二次确认落库）。幂等：已下发重复确认返回现状，不重复写。"""
    with get_write_session() as s:
        wo = s.get(models.WorkOrder, order_id)
        if wo is None:
            return {"found": False}
        if wo.status == "已下发":
            return {"order_id": order_id, "status": wo.status, "duplicate": True}
        if wo.status != "草稿":
            return {"found": True, "error": f"工单状态[{wo.status}]不可确认"}
        wo.status = "已下发"
        wo.confirm_user = user_id
        wo.confirm_time = datetime.now(timezone.utc)
        wo.updated_at = datetime.now(timezone.utc)
        s.commit()
        return {"order_id": order_id, "status": wo.status}


def cancel_work_order(order_id: str) -> dict:
    """草稿 → 已取消。幂等：已取消重复取消返回现状。"""
    with get_write_session() as s:
        wo = s.get(models.WorkOrder, order_id)
        if wo is None:
            return {"found": False}
        if wo.status == "已取消":
            return {"order_id": order_id, "status": wo.status, "duplicate": True}
        if wo.status != "草稿":
            return {"found": True, "error": f"工单状态[{wo.status}]不可取消"}
        wo.status = "已取消"
        wo.updated_at = datetime.now(timezone.utc)
        s.commit()
        return {"order_id": order_id, "status": wo.status}


def list_devices(keyword: str | None = None, limit: int = 50) -> list[dict]:
    """设备列表 + 模糊搜索（按名称/站所/类型）。"""
    with get_read_session() as s:
        q = s.query(models.Device)
        if keyword:
            like = f"%{keyword}%"
            q = q.filter(
                models.Device.device_name.like(like)
                | models.Device.station.like(like)
                | models.Device.device_type.like(like)
                | models.Device.device_id.like(like)
            )
        rows = q.order_by(models.Device.device_id).limit(limit).all()
        return [
            {
                "device_id": r.device_id,
                "device_name": r.device_name,
                "device_type": r.device_type,
                "station": r.station,
                "status": r.status,
            }
            for r in rows
        ]


def list_sessions(user_id: str | None = None, start=None, end=None, limit: int = 50, offset: int = 0) -> list[dict]:
    """会话列表（按用户/时间/分页）。"""
    with get_read_session() as s:
        q = s.query(models.Session)
        if user_id:
            q = q.filter_by(user_id=user_id)
        if start:
            q = q.filter(models.Session.created_at >= _parse_dt(start))
        if end:
            q = q.filter(models.Session.created_at <= _parse_dt(end))
        rows = q.order_by(models.Session.created_at.desc()).offset(offset).limit(limit).all()
        return [
            {"session_id": r.session_id, "user_id": r.user_id, "intent": r.intent, "created_at": r.created_at.isoformat()}
            for r in rows
        ]


def list_defects(level: str | None = None, device_id: str | None = None, start=None, end=None, limit: int = 50, offset: int = 0) -> list[dict]:
    """缺陷列表（按等级/设备/时间/分页）。"""
    with get_read_session() as s:
        q = s.query(models.Defect)
        if level:
            q = q.filter_by(level=level)
        if device_id:
            q = q.filter_by(device_id=device_id)
        if start:
            q = q.filter(models.Defect.discover_time >= _parse_dt(start))
        if end:
            q = q.filter(models.Defect.discover_time <= _parse_dt(end))
        rows = q.order_by(models.Defect.discover_time.desc()).offset(offset).limit(limit).all()
        return [
            {"defect_id": r.defect_id, "device_id": r.device_id, "description": r.description,
             "level": r.level, "status": r.status, "source": r.source}
            for r in rows
        ]


def list_work_orders(level: str | None = None, device_id: str | None = None, start=None, end=None, limit: int = 50, offset: int = 0) -> list[dict]:
    """工单列表（按等级/设备/时间/分页）。"""
    with get_read_session() as s:
        q = s.query(models.WorkOrder)
        if level:
            q = q.filter_by(level=level)
        if device_id:
            q = q.filter(models.WorkOrder.ref_id == device_id)
        if start:
            q = q.filter(models.WorkOrder.created_at >= _parse_dt(start))
        if end:
            q = q.filter(models.WorkOrder.created_at <= _parse_dt(end))
        rows = q.order_by(models.WorkOrder.created_at.desc()).offset(offset).limit(limit).all()
        return [
            {"order_id": r.order_id, "ref_type": r.ref_type, "ref_id": r.ref_id, "content": r.content,
             "level": r.level, "status": r.status, "assignee": r.assignee,
             "deadline": r.deadline.isoformat() if r.deadline else None}
            for r in rows
        ]


def get_traces(session_id: str, start=None, end=None) -> list[dict]:
    with get_read_session() as s:
        q = s.query(models.Trace).filter_by(session_id=session_id)
        if start:
            q = q.filter(models.Trace.created_at >= _parse_dt(start))
        if end:
            q = q.filter(models.Trace.created_at <= _parse_dt(end))
        rows = q.order_by(models.Trace.step).all()
        return [
            {
                "step": r.step,
                "tool": r.tool,
                "params": r.params,
                "result": r.result,
                "sources": r.sources,
                "elapsed_ms": r.elapsed_ms,
                "degraded": r.degraded,
            }
            for r in rows
        ]


def append_message(session_id: str, role: str, content: str) -> None:
    """持久化一条会话消息（写穿，供多轮历史扛 Redis 重启）。"""
    with get_write_session() as s:
        s.add(models.Message(
            message_id=uuid.uuid4().hex,
            session_id=session_id,
            role=role,
            content=content,
        ))
        s.commit()


def get_messages(session_id: str, k: int = 20) -> list[dict]:
    """按时间升序返回最近 k 条消息（旧→新，供 LLM 上下文）。"""
    with get_read_session() as s:
        rows = (
            s.query(models.Message)
            .filter_by(session_id=session_id)
            .order_by(models.Message.created_at.desc())
            .limit(k)
            .all()
        )
        return [{"role": r.role, "content": r.content} for r in reversed(rows)]


def list_messages(session_id: str | None = None, start=None, end=None, limit: int = 50, offset: int = 0) -> list[dict]:
    """消息列表（按会话/时间/分页，供历史回看）。"""
    with get_read_session() as s:
        q = s.query(models.Message)
        if session_id:
            q = q.filter_by(session_id=session_id)
        if start:
            q = q.filter(models.Message.created_at >= _parse_dt(start))
        if end:
            q = q.filter(models.Message.created_at <= _parse_dt(end))
        rows = q.order_by(models.Message.created_at.desc()).offset(offset).limit(limit).all()
        return [
            {"message_id": r.message_id, "session_id": r.session_id, "role": r.role,
             "content": r.content, "created_at": r.created_at.isoformat()}
            for r in rows
        ]


# --------------------------------------------------------------------------
# 复盘案例库（长期记忆）
# --------------------------------------------------------------------------

def _case_to_dict(r) -> dict:
    return {
        "case_id": r.case_id,
        "title": r.title,
        "device_type": r.device_type,
        "symptom": r.symptom,
        "root_cause": r.root_cause,
        "action": r.action,
        "basis_refs": r.basis_refs,
        "source_type": r.source_type,
        "source_ref_id": r.source_ref_id,
        "status": r.status,
        "version": r.version,
        "superseded_by": r.superseded_by,
        "created_at": r.created_at.isoformat() if r.created_at else None,
    }


def create_review_case(case: dict) -> dict:
    """落库一条复盘案例（自动沉淀后 status=草稿，待人工审核）。"""
    with get_write_session() as s:
        data = dict(case)
        data.setdefault("case_id", f"RC{uuid.uuid4().hex[:24]}")
        data.setdefault("status", "草稿")
        data.setdefault("version", "1.0.0")
        rc = models.ReviewCase(**data)
        s.add(rc)
        s.commit()
        return {"case_id": rc.case_id, "status": rc.status}


def list_review_cases(status: str | None = None, device_type: str | None = None, limit: int = 50, offset: int = 0) -> list[dict]:
    with get_read_session() as s:
        q = s.query(models.ReviewCase)
        if status:
            q = q.filter_by(status=status)
        if device_type:
            q = q.filter_by(device_type=device_type)
        rows = q.order_by(models.ReviewCase.created_at.desc()).offset(offset).limit(limit).all()
        return [_case_to_dict(r) for r in rows]


def search_review_cases(query: str, device_type: str | None = None, limit: int = 8) -> list[dict]:
    """Agent 检索：只返回「已审核且未废止」的当前版本，关键词匹配现象/根因/处置。"""
    terms = _keyword_terms(query)
    with get_read_session() as s:
        q = s.query(models.ReviewCase).filter(
            models.ReviewCase.status == "已审核",
            models.ReviewCase.superseded_by.is_(None),
        )
        if device_type:
            q = q.filter_by(device_type=device_type)
        rows = q.order_by(models.ReviewCase.updated_at.desc()).limit(200).all()
    result = []
    for r in rows:
        hay = f"{r.symptom} {r.root_cause or ''} {r.action} {r.title}".lower()
        if terms and not all(t in hay for t in terms):
            continue
        result.append(_case_to_dict(r))
        if len(result) >= limit:
            break
    return result


def approve_review_case(case_id: str, reviewer: str) -> dict:
    with get_write_session() as s:
        rc = s.get(models.ReviewCase, case_id)
        if rc is None:
            return {"found": False}
        rc.status = "已审核"
        rc.reviewer = reviewer
        rc.reviewed_at = datetime.now(timezone.utc)
        rc.effective_date = rc.effective_date or rc.reviewed_at
        s.commit()
        return {"case_id": case_id, "status": rc.status}


def reject_review_case(case_id: str, reviewer: str) -> dict:
    with get_write_session() as s:
        rc = s.get(models.ReviewCase, case_id)
        if rc is None:
            return {"found": False}
        rc.status = "已驳回"
        rc.reviewer = reviewer
        rc.reviewed_at = datetime.now(timezone.utc)
        s.commit()
        return {"case_id": case_id, "status": rc.status}


def supersede_review_case(case_id: str, new_case_id: str | None = None, reviewer: str | None = None) -> dict:
    """废止旧案例：status=已废止 + superseded_by 指向新案例（版本治理）。"""
    with get_write_session() as s:
        rc = s.get(models.ReviewCase, case_id)
        if rc is None:
            return {"found": False}
        rc.status = "已废止"
        rc.superseded_by = new_case_id
        if reviewer:
            rc.reviewer = reviewer
            rc.reviewed_at = datetime.now(timezone.utc)
        s.commit()
        return {"case_id": case_id, "status": rc.status, "superseded_by": new_case_id}


def latest_diagnosis(session_id: str) -> dict | None:
    """会话内最近一次诊断/状态结果（供案例沉淀的根因/依据）。"""
    with get_read_session() as s:
        row = (
            s.query(models.Trace)
            .filter(
                models.Trace.session_id == session_id,
                models.Trace.tool.in_(("diagnose", "query_state")),
            )
            .order_by(models.Trace.step.desc())
            .first()
        )
        return row.result if row else None


def _keyword_terms(query: str) -> list[str]:
    if not query:
        return []
    return [t for t in str(query).strip().lower().split() if t]


def get_agent_metrics() -> dict:
    """Agent 运行指标聚合（可观测/监控）。

    返回请求量、工具调用、LLM 调用、降级、产出量等关键指标；token/成本取最近一次
    运行的累计值（per-run 记账，精确总账需另行聚合）。
    """
    with get_read_session() as s:
        sessions = s.query(models.Session).count()
        messages = s.query(models.Message).count()
        tool_calls = s.query(models.Trace).filter(models.Trace.tool.isnot(None)).count()
        avg_latency = s.query(func.avg(models.Trace.elapsed_ms)).scalar() or 0.0
        degraded = s.query(models.Trace).filter_by(degraded=True).count()
        model_calls = s.query(models.BudgetRecord).filter_by(event="reserve").count()
        latest_budget = (
            s.query(models.BudgetRecord)
            .filter_by(event="reconcile")
            .order_by(models.BudgetRecord.created_at.desc())
            .first()
        )
        evidence = s.query(models.EvidenceRecord).count()
        workorders = s.query(models.WorkOrder).count()
        review_cases = s.query(models.ReviewCase).count()
    return {
        "sessions": sessions,
        "messages": messages,
        "tool_calls": tool_calls,
        "avg_tool_latency_ms": round(float(avg_latency), 1),
        "degraded_tool_calls": degraded,
        "model_calls": model_calls,
        "charged_tokens_latest_run": int(latest_budget.charged_tokens) if latest_budget else 0,
        "charged_cost_rmb_latest_run": round(float(latest_budget.charged_cost), 6) if latest_budget else 0.0,
        "evidence_count": evidence,
        "workorders": workorders,
        "review_cases": review_cases,
    }


def save_eval_run(
    suite: str,
    metrics: dict,
    sample_n: int = 0,
    note: str | None = None,
    run_id: str | None = None,
) -> dict:
    """固化一次离线评测结果（检索/定级/压力），供评估看板读取。"""
    with get_write_session() as s:
        rid = run_id or f"EV{uuid.uuid4().hex[:24]}"
        row = models.EvalRun(run_id=rid, suite=suite, sample_n=sample_n, metrics=metrics, note=note)
        s.add(row)
        s.commit()
        return {"run_id": rid, "suite": suite}


def list_eval_runs(limit: int = 20) -> list[dict]:
    with get_read_session() as s:
        rows = s.query(models.EvalRun).order_by(models.EvalRun.created_at.desc()).limit(limit).all()
        return [
            {
                "run_id": r.run_id,
                "suite": r.suite,
                "sample_n": r.sample_n,
                "metrics": r.metrics,
                "note": r.note,
                "created_at": r.created_at.isoformat() if r.created_at else None,
            }
            for r in rows
        ]


def eval_summary() -> dict:
    """每个评测套件取最新一次运行，汇总为 {suite: latest_run}。"""
    with get_read_session() as s:
        rows = s.query(models.EvalRun).order_by(models.EvalRun.created_at.desc()).all()
    latest: dict[str, dict] = {}
    for r in rows:
        if r.suite not in latest:
            latest[r.suite] = {
                "run_id": r.run_id,
                "sample_n": r.sample_n,
                "metrics": r.metrics,
                "note": r.note,
                "created_at": r.created_at.isoformat() if r.created_at else None,
            }
    return latest
