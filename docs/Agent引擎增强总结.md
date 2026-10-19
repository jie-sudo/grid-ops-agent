# Agent 引擎增强总结（M7~M7d）

> 电网智能运维 Agent 在 M0~M6（骨架/规则/工具/引擎/接口/评估）之后的引擎增强轮，
> 借鉴开源项目 AegisOps 的三项生产级机制，适配到自研轻量 ReAct 架构。
> 对应设计文档：《历史数据保留与复盘案例库设计.md》。测试：38 个纯逻辑单测（不需 DB/LLM）。

---

## 1. 概述

M7 系列把引擎从"能用"补到"生产级"，围绕三条安全/可靠性主线：

| 里程碑 | 主题 | 借鉴 | 对应原则 |
|---|---|---|---|
| M7 | 证据账本 + 预算账本 | AegisOps verify_report / BudgetLedger | C1 防幻觉、控成本 |
| M7b | 中断恢复（checkpoint + 幂等 + 锁） | AegisOps checkpoint/lease/idempotency | C2 写操作安全 |
| M7c | 会话历史持久化 | — | 多轮上下文不丢 |
| M7d | 历史保留 + 复盘案例库 | AegisOps 复盘知识/案例复用 | "3 年后还能知道" |

---

## 2. 证据账本与溯源（M7，防幻觉）

**`app/engine/evidence.py`**：每次工具返回登记为证据记录（SHA256 内容哈希 + 稳定 evidence_id），最终回答经过 `verify_report` 三重校验，不拦截、只标注：

1. 用到知识/诊断工具却无来源 → 提示"结论缺少来源"；
2. 来源字符串无法追溯到证据账本（知识出处/证据 ID/点名了实际调用的工具）→ 提示"来源无法溯源"；
3. 答案里 >1 的数值无法追溯到「用户输入 ∪ 工具参数 ∪ 工具返回」→ 提示"数值无法溯源"。

**关键设计**：来源解析用"是否点名了实际调用的工具"做宽松匹配（自然语言来源不是证据 ID），数值溯源纳入**用户输入 + 工具参数**（修过"用户说的数字被误标"的坑）。

---

## 3. 预算账本（M7，控成本）

**`app/engine/budget.py`**：预留式记账——每次 LLM 调用前先预留（请求数 + 估算 Token + 费用），超限抛 `BudgetExceeded`；调用后按供应商 usage 结算，**usage 缺失时保留预留、绝不当作零**。支持请求数/Token/费用三档限额。

**关键设计**：同步单请求架构下用进程内状态即可，持久化 best-effort（表未建不阻断）；LLM 失败调用把 `last_usage` 重置为 None，避免用上一次的 usage 结算。

---

## 4. 中断恢复（M7b，写操作安全）

三件套，对应 AegisOps 的 checkpoint + lease + idempotency：

1. **检查点**（`app/engine/checkpoint.py` 的 `CheckpointStore`）：工单挂起态 + 实体锚点落 PG，Redis 丢失后下次请求可从 PG 恢复，避免"确认状态丢失"；
2. **幂等落库**：`WorkOrder` 加 `idempotency_key`（唯一），`create_work_order` 重复确认直接返回已有工单，防"进程死在写库瞬间、重试导致重复工单"；
3. **会话锁**（`session_lock`）：PG advisory lock（`hashtext` 跨进程稳定键）串行化同一会话的并发请求。

**关键设计**：`run()` 拆成 `run`（加锁）+ `_run_impl`（主循环）；`database.py` 加 `apply_migrations()`（幂等 DDL），`python -m app.data.database` 一次完成建表+补列+授权。

---

## 5. 会话历史持久化（M7c）

多轮对话历史写穿 PG（用起预留的 `Message` 表）：`Memory.append_history` 写穿 PG+Redis，`get_history` 优先 Redis、命中空/不可用回读 PG。**关键设计**：Redis 是快缓存、PG 是真相源，重启后第一条消息进来就能靠 PG 兜住完整历史。

---

## 6. 历史保留 + 复盘案例库（M7d，"3 年后还能知道"）

**历史保留**：四张流水表（Message/Trace/EvidenceRecord/BudgetRecord）加 created_at 索引 + `scripts/archive_history.py` 归档脚本（超热区挪到 `*_archive` 冷表）+ 历史查询接口加 start/end/limit/offset。

**复盘案例库**：`ReviewCase` 表 + `skills/review_case.py` 规则提炼（`draft_from_workorder`，不调 LLM）+ 审核 API（通过/驳回/废止，带版本+废止链）+ `search_review_cases` 工具 + react_loop 在工单确认后自动沉淀草稿。前端加「复盘案例」tab。

**关键设计**：案例与规程同一套版本治理（`status`/`superseded_by`），Agent 只检索"已审核且未废止"的当前版本。

---

## 7. 工单生成确定性快路径 + 意图定向提示

两个引擎行为优化（都在 `react_loop.py`）：

1. **确定性快路径**（`_workorder_fastpath`）：「工单生成」意图绕过 LLM 的 ReAct 循环，直接确定性编排——提取设备编号 → 定级（原文等级 → query_state 映射 → grade_defect → 反问）→ 调 `create_workorder_draft` → 走二次确认闸口。0 轮 LLM，稳、快、安全；
2. **意图定向提示**（`INTENT_HINTS`）：把检测到的意图作为软提示注入 system prompt，减少"先大范围取证再动手"的过度工具调用（软先验，不锁工具）。

---

## 8. 关键结论

1. **安全靠架构兜底，不靠模型听话**——写操作靠"闸口 + DB 权限"物理隔离，数值靠"工具 + 溯源"，不确定靠"反问 + 降级"；LLM 被骗了也做不了坏事；
2. **确定性计算走规则、LLM 只编排**——分级/诊断/定级是规则引擎，LLM 不碰数值；工单快路径把"意图单一、参数明确"的任务从 LLM 手里收回来，稳又快；
3. **新表/新列要重跑 `python -m app.data.database`**（create_all 只建新表，`apply_migrations` 补列补索引，`init_roles` 对新表重新授权）；
4. **持久化 best-effort 是刻意的**——审计/检查点落 PG，但库不可用时不阻断主流程，进程内校验仍然成立。
