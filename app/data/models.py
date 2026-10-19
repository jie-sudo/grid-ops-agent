"""ORM 模型：业务表（DR-001~007）+ 引擎支撑表（用户/会话/追溯/消息/摘要）。

对应 SRS 数据字典与 SDD 5.1 / 5.2。主键均为业务编号字符串（非自增）。
"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, Index, JSON, String, Text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


def _now() -> datetime:
    return datetime.now()


# --------------------------------------------------------------------------
# 业务表
# --------------------------------------------------------------------------

class Device(Base):
    """DR-001 设备台账。"""

    __tablename__ = "device"

    device_id: Mapped[str] = mapped_column(String(32), primary_key=True)
    device_name: Mapped[str] = mapped_column(String(64), nullable=False)
    device_type: Mapped[str] = mapped_column(String(32), nullable=False, index=True)  # 变压器/开关柜/电缆/线路/断路器/其他
    voltage_level: Mapped[str] = mapped_column(String(32), nullable=False)  # 10kV/35kV/110kV/220kV/其他
    station: Mapped[str | None] = mapped_column(String(64))
    commission_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    rated_params: Mapped[dict | None] = mapped_column(JSON)  # 额定参数（电压/电流/容量等）
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="运行")  # 运行/停运/检修/备用
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)


class MeasurePoint(Base):
    """DR-002 量测点定义。"""

    __tablename__ = "measure_point"

    point_id: Mapped[str] = mapped_column(String(32), primary_key=True)
    device_id: Mapped[str] = mapped_column(String(32), ForeignKey("device.device_id"), nullable=False)
    measure_type: Mapped[str] = mapped_column(String(32), nullable=False)  # 温度/电流/电压/局放/护层电流/油色谱/其他
    unit: Mapped[str | None] = mapped_column(String(8))
    threshold_upper: Mapped[float | None] = mapped_column(Float)
    threshold_lower: Mapped[float | None] = mapped_column(Float)
    latest_value: Mapped[float | None] = mapped_column(Float)  # 最新值（冗余缓存，非历史）
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)

    __table_args__ = (Index("ix_measure_point_device_type", "device_id", "measure_type"),)


class MeasureValue(Base):
    """DR-003 量测时序数据（分表存储，按月分区建议）。"""

    __tablename__ = "measure_value"

    value_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    point_id: Mapped[str] = mapped_column(String(32), ForeignKey("measure_point.point_id"), nullable=False)
    ts: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    value: Mapped[float | None] = mapped_column(Float)  # 缺失/无效时为 null，由 quality 标记
    quality: Mapped[str | None] = mapped_column(String(16))  # 正常/越限/缺失/无效

    __table_args__ = (Index("ix_measure_value_point_ts", "point_id", "ts"),)


class Defect(Base):
    """DR-004 缺陷。"""

    __tablename__ = "defect"

    defect_id: Mapped[str] = mapped_column(String(32), primary_key=True)
    device_id: Mapped[str] = mapped_column(String(32), ForeignKey("device.device_id"), nullable=False)
    location: Mapped[str | None] = mapped_column(String(128))
    description: Mapped[str] = mapped_column(String(512), nullable=False)
    level: Mapped[str] = mapped_column(String(16), nullable=False, index=True)  # 一般/严重/危急
    discover_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    deadline: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))  # 分级后生成，可为空
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="待处理", index=True)  # 待处理/处理中/已消除/已验收
    source: Mapped[str] = mapped_column(String(16), nullable=False, default="巡检")  # 巡检/告警/诊断/试验


class Alarm(Base):
    """DR-005 告警。"""

    __tablename__ = "alarm"

    alarm_id: Mapped[str] = mapped_column(String(32), primary_key=True)
    device_id: Mapped[str] = mapped_column(String(32), ForeignKey("device.device_id"), nullable=False)
    alarm_type: Mapped[str] = mapped_column(String(32), nullable=False)  # 过温/过流/局放/越限/其他
    level: Mapped[str] = mapped_column(String(16), nullable=False, index=True)  # 提示/重要/紧急
    trigger_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, index=True)
    related_point: Mapped[str | None] = mapped_column(String(32), ForeignKey("measure_point.point_id"))
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="活动")  # 活动/已确认/已恢复


class WorkOrder(Base):
    """DR-006 工单。"""

    __tablename__ = "work_order"

    order_id: Mapped[str] = mapped_column(String(32), primary_key=True)
    ref_type: Mapped[str] = mapped_column(String(16), nullable=False)  # 缺陷/告警/任务
    ref_id: Mapped[str | None] = mapped_column(String(32))
    content: Mapped[str] = mapped_column(String(1024), nullable=False)
    level: Mapped[str] = mapped_column(String(16), nullable=False)  # 一般/严重/危急
    deadline: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    assignee: Mapped[str | None] = mapped_column(String(32))
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="草稿")  # 草稿/待确认/已下发/处理中/已验收
    confirm_user: Mapped[str | None] = mapped_column(String(32))  # 确认人（二次确认）
    confirm_time: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    idempotency_key: Mapped[str | None] = mapped_column(String(64), unique=True)  # 幂等键（防重复落库）
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)

    __table_args__ = (Index("ix_work_order_ref", "ref_type", "ref_id"),)


class KnowledgeDoc(Base):
    """DR-007 知识文档。"""

    __tablename__ = "knowledge_doc"

    doc_id: Mapped[str] = mapped_column(String(32), primary_key=True)
    title: Mapped[str] = mapped_column(String(128), nullable=False)
    doc_type: Mapped[str] = mapped_column(String(16), nullable=False)  # 规程/案例/处置卡/标准
    device_domain: Mapped[str] = mapped_column(String(32), nullable=False, index=True)  # 变压器/开关柜/电缆/线路/通用
    content: Mapped[str] = mapped_column(Text, nullable=False)
    source: Mapped[str | None] = mapped_column(String(128))  # 来源（标准编号等）
    tags: Mapped[list | None] = mapped_column(JSON)
    vector_id: Mapped[str | None] = mapped_column(String(64))


# --------------------------------------------------------------------------
# 引擎支撑表
# --------------------------------------------------------------------------

class AppUser(Base):
    """RBAC 鉴权用户。"""

    __tablename__ = "app_user"

    user_id: Mapped[str] = mapped_column(String(32), primary_key=True)
    username: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    role: Mapped[str] = mapped_column(String(16), nullable=False)  # operator/monitor/manager/admin
    password_hash: Mapped[str] = mapped_column(String(128), nullable=False)


class Session(Base):
    """会话级追溯。"""

    __tablename__ = "session"

    session_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    user_id: Mapped[str | None] = mapped_column(String(32), ForeignKey("app_user.user_id"))
    intent: Mapped[str | None] = mapped_column(String(32))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)


class Trace(Base):
    """步骤级追溯。"""

    __tablename__ = "trace"

    trace_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    session_id: Mapped[str] = mapped_column(String(64), ForeignKey("session.session_id"), nullable=False)
    step: Mapped[int] = mapped_column(nullable=False)
    tool: Mapped[str | None] = mapped_column(String(64))
    params: Mapped[dict | None] = mapped_column(JSON)
    result: Mapped[dict | None] = mapped_column(JSON)
    sources: Mapped[list | None] = mapped_column(JSON)
    elapsed_ms: Mapped[int | None] = mapped_column()
    degraded: Mapped[bool] = mapped_column(default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, index=True)


class Message(Base):
    """会话历史（多轮持久化）。"""

    __tablename__ = "message"

    message_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    session_id: Mapped[str] = mapped_column(String(64), ForeignKey("session.session_id"), nullable=False)
    role: Mapped[str] = mapped_column(String(16), nullable=False)  # user/assistant
    content: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, index=True)

    __table_args__ = (Index("ix_message_session", "session_id", "created_at"),)


class SessionSummary(Base):
    """会话摘要（压缩窗口外历史）。"""

    __tablename__ = "session_summary"

    session_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    summary: Mapped[str | None] = mapped_column(Text)
    anchors: Mapped[dict | None] = mapped_column(JSON)  # 实体锚点（设备编号/缺陷等级等）
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)


class EvidenceRecord(Base):
    """证据账本（审计）：工具返回的内容哈希，供最终回答溯源。"""

    __tablename__ = "evidence_record"

    evidence_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    session_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    tool: Mapped[str] = mapped_column(String(64), nullable=False)
    params_hash: Mapped[str | None] = mapped_column(String(64))
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    result: Mapped[str | None] = mapped_column(Text)  # 截断后的规范 JSON（审计用）
    degraded: Mapped[bool] = mapped_column(default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, index=True)


class BudgetRecord(Base):
    """预算账本（审计）：预留式记账事件（reserve / reconcile）。"""

    __tablename__ = "budget_record"

    record_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    run_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    session_id: Mapped[str | None] = mapped_column(String(64))
    event: Mapped[str] = mapped_column(String(16), nullable=False)  # reserve/reconcile
    requests: Mapped[int] = mapped_column(default=0)
    charged_tokens: Mapped[int] = mapped_column(default=0)
    charged_cost: Mapped[float] = mapped_column(Float, default=0.0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, index=True)


class RunCheckpoint(Base):
    """中断恢复检查点：会话挂起态（待确认工单）与实体锚点落 PG。

    Redis 丢失 / 进程重启后，下次请求可从该表恢复挂起态，避免
    "确认状态丢失"与"重复落库"。
    """

    __tablename__ = "run_checkpoint"

    session_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    run_id: Mapped[str] = mapped_column(String(64), nullable=False)
    step: Mapped[int] = mapped_column(default=0)
    intent: Mapped[str | None] = mapped_column(String(32))
    awaiting_confirm: Mapped[bool] = mapped_column(default=False)
    draft: Mapped[dict | None] = mapped_column(JSON)  # 待确认的工单草稿
    anchors: Mapped[dict | None] = mapped_column(JSON)  # 实体锚点（设备编号等）
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)


class ReviewCase(Base):
    """复盘案例库：从已关闭工单/诊断沉淀的可复用经验（长期记忆）。

    与知识库同一套版本治理：草稿 → 已审核 → 已废止（superseded_by 指向新案例），
    Agent 检索时只返回「已审核且未废止」的当前版本。
    """

    __tablename__ = "review_case"

    case_id: Mapped[str] = mapped_column(String(32), primary_key=True)
    title: Mapped[str] = mapped_column(String(128), nullable=False)
    device_type: Mapped[str] = mapped_column(String(32), nullable=False, index=True)  # 变压器/开关柜/电缆/通用
    symptom: Mapped[str] = mapped_column(String(512), nullable=False)  # 现象描述
    root_cause: Mapped[str | None] = mapped_column(String(512))  # 根因（待核实时为空）
    action: Mapped[str] = mapped_column(String(1024), default="")  # 处置措施
    basis_refs: Mapped[list | None] = mapped_column(JSON)  # 依据（知识出处/证据/工单）
    source_type: Mapped[str] = mapped_column(String(16), nullable=False)  # 工单/诊断/人工
    source_ref_id: Mapped[str | None] = mapped_column(String(32))  # 关联工单/缺陷ID
    session_id: Mapped[str | None] = mapped_column(String(64))
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="草稿", index=True)  # 草稿/已审核/已废止
    version: Mapped[str] = mapped_column(String(16), nullable=False, default="1.0.0")
    effective_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    superseded_by: Mapped[str | None] = mapped_column(String(32))
    reviewer: Mapped[str | None] = mapped_column(String(32))
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, index=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)


class EvalRun(Base):
    """评估运行记录：离线评测脚本（检索/定级/压力）的结果固化，供评估看板展示。

    评测是重离线计算（加载嵌入模型、跑全量语料），不适合每次请求实时重跑；
    脚本跑完后把关键指标 save_eval_run 落库，评估看板（GET /evals/summary）读最新。
    """

    __tablename__ = "eval_run"

    run_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    suite: Mapped[str] = mapped_column(String(32), nullable=False, index=True)  # retrieval/grading/stress
    sample_n: Mapped[int] = mapped_column(default=0)
    metrics: Mapped[dict | None] = mapped_column(JSON)  # 指标（R@5/R@10、命中率/降级率/误判率等）
    note: Mapped[str | None] = mapped_column(String(256))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, index=True)
