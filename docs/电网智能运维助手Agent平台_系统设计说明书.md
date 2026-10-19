# 电网智能运维助手 Agent 平台
# 系统设计说明书（SDD）

| 项目 | 内容 |
|------|------|
| 文档编号 | SDD-GRID-OPS-AGENT |
| 版本 | v0.4 |
| 编制日期 | 2026-10-14 |
| 状态 | 待评审 |
| 密级 | 内部 |
| 关联文档 | SRS-GRID-OPS-AGENT v1.2 |

---

## 修订记录

| 版本 | 日期 | 修订说明 | 作者 |
|------|------|---------|------|
| v0.1 | 2026-10-14 | 初稿：总体架构、技术选型、模块设计、数据模型、接口、时序、安全、部署 | — |
| v0.2 | 2026-10-14 | 关闭三项遗留：向量化模型多候选评测选优、前端静态 Web Demo、会话状态 Redis 外置 + api 多实例 | — |
| v0.3 | 2026-10-14 | 补充多轮会话记忆管理（4.1.6）：三层记忆、上下文窗口、message/session_summary 表、Redis 键约定 | — |
| v0.4 | 2026-10-14 | 工程化加固：数据库只读角色分离（8.5）、RAG 新旧语料版本治理（5.3）、ADR-010/011 | — |

---

## 1 设计概述

### 1.1 设计目标

依据 SRS v1.2，完成"电网智能运维助手 Agent 平台"的系统设计，达到可直接指导开发与测试的粒度。设计围绕三个关键词展开：**通用引擎、可插拔技能包、确定性优先**。

### 1.2 设计原则

| 原则 | 来源 | 落地方式 |
|------|------|---------|
| P1 确定性优先 | SRS C1 | 分级/映射/诊断等确定性计算全部走规则引擎，LLM 仅负责编排与解释 |
| P2 写操作闸口 | SRS C2 | 任何写操作在主循环内挂起，经用户二次确认后才落库 |
| P3 降级不编造 | SRS C3 | 数据不足/超适用条件时强制降级为"建议人工复核" |
| P4 全程可追溯 | SRS FR-005/NFR-005 | 每个结论附来源，调用链、耗时、降级标记全量落库 |
| P5 框架通用 | SRS FR-050/NFR-007 | 引擎与数据模型复用，新场景只加技能包 |
| P6 接口可替换 | SRS NFR-009 | LLM、向量库、结构化库均通过接口抽象 |

### 1.3 与 SRS 的对应关系

本文档章节与 SRS 需求编号的映射（用于追踪）：

| 本文档 | 覆盖的 SRS 需求 |
|--------|----------------|
| 2 总体架构 | FR-001~005、FR-050 |
| 4.1 Agent 引擎 | FR-001~005 |
| 4.2 技能包框架 | FR-050~052 |
| 4.3 业务能力 | FR-010~062 |
| 4.4 规则引擎 | BR-001~006、FR-031/040/041 |
| 5 数据模型 | DR-001~007 |
| 6 接口设计 | IF-001~004 |
| 8 安全设计 | NFR-004~006、第 8 章权限矩阵 |
| 9 非功能设计 | NFR-001~009 |
| 10 部署方案 | 2.3 运行环境 |

---

## 2 总体架构

### 2.1 分层架构图

```mermaid
flowchart TB
    subgraph CLIENT["接入层"]
        WEB["Web Demo 前端"]
        TP["第三方客户端"]
    end

    subgraph API["API 层（FastAPI，可水平扩展）"]
        AUTH["鉴权 JWT + RBAC"]
        RL["限流"]
        CHAT["对话入口 /api/v1/chat"]
        REST["REST 资源接口"]
    end

    subgraph ENGINE["Agent 引擎（自研）"]
        IR["意图路由 IntentRouter"]
        LOOP["ReAct 主控循环 AgentLoop"]
        TD["工具调度器 ToolDispatcher"]
        GUARD["安全闸口 Guards"]
        TRACE["追溯器 Tracer"]
    end

    subgraph SKILLS["能力层"]
        RAG["RAG 问答"]
        QUERY["状态/告警查询"]
        DEFECT["缺陷分级（规则引擎）"]
        DIAG["故障诊断"]
        WO["工单服务"]
    end

    subgraph PACK["技能包层"]
        P1["switchgear-pack"]
        P2["transformer-pack"]
        P3["cable-pack"]
    end

    subgraph DATA["数据层"]
        PG[("PostgreSQL")]
        VEC[("ChromaDB")]
        REDIS[("Redis（会话状态）")]
        ADP["数据接入适配器"]
    end

    LLM["LLM（OpenAI 兼容，DeepSeek 默认）"]

    WEB --> AUTH
    TP --> AUTH
    AUTH --> RL
    RL --> CHAT
    RL --> REST
    CHAT --> IR --> LOOP
    LOOP <--> LLM
    LOOP --> TD --> GUARD --> TRACE
    LOOP -.->|会话状态| REDIS
    TD --> SKILLS
    DEFECT --> PACK
    DIAG --> PACK
    RAG --> VEC
    SKILLS --> PG
    ADP --> PG
    ADP -.->|预留| PMS["PMS / 监测系统"]
```

### 2.2 组件清单与职责

| 组件 | 职责 | 关键输入/输出 |
|------|------|--------------|
| 意图路由 IntentRouter | 七类意图分类 + 低置信澄清 | 文本 → 意图标签 + 置信度 |
| ReAct 主控循环 AgentLoop | 推理-行动-观察循环，步数上限 6 | 意图 → 最终结论 |
| 工具调度器 ToolDispatcher | 工具注册表校验、schema 校验、执行、结果序列化 | 工具名+参数 → 结构化结果 |
| 安全闸口 Guards | 二次确认挂起、降级判定、输出校验 | 写操作/诊断 → 放行或拦截 |
| 追溯器 Tracer | 会话级调用链、来源、耗时、降级标记落库 | 全链路日志 |
| 规则引擎 RuleEngine | 分级/映射/时限等确定性计算 | 数据 → 等级 + 依据 |
| 技能包 SkillPack | 设备域专属查询工具 + 诊断规则 + 阈值 + 知识 | 设备类型 → 能力集 |
| 数据接入适配器 | CSV/JSON 归一化，预留 PMS | 外部数据 → 内部模型 |

### 2.3 技术选型总表

| 层 | 选型 | 版本/说明 | 备注 |
|----|------|----------|------|
| 语言 | Python | 3.10+ | 本地 SAM2 环境 3.10 / Docker 3.11 |
| Web 框架 | FastAPI + uvicorn | 最新稳定版 | REST + 异步 |
| Agent 编排 | 自研 ReAct 主循环 | — | 无 LangChain/LlamaIndex 依赖（见 ADR-001） |
| LLM 接入 | httpx（OpenAI 兼容协议） | 默认 DeepSeek | 可替换，见 IF-002 |
| 结构化存储 | PostgreSQL | 16+ | psycopg3 + SQLAlchemy 2.0 |
| 向量库 | ChromaDB | 默认 | 预留 FAISS 适配器 |
| 向量化模型 | 通用 embedding（多候选评测） | 评测选优 | 见 5.5 / ADR-007 |
| 会话状态 | Redis | 7.x | 多实例共享挂起态 |
| 前端 | 静态 Web Demo | HTML/JS（或 Vue） | 前后端分离 |
| 数据接入 | pandas + 适配器 | — | CSV/JSON |
| 鉴权 | python-jose + passlib | JWT HS256 | role 声明 |
| 校验/序列化 | pydantic v2 | — | schema 校验 |
| 测试 | pytest + 评估脚本 | — | 单测 + 评估集 |

---

## 3 代码目录结构

```
grid-ops-agent/
├── app/
│   ├── main.py                # FastAPI 入口、路由装配
│   ├── config.py              # 配置加载（环境变量优先）
│   ├── api/                   # 路由层
│   │   ├── chat.py            # /api/v1/chat 对话入口
│   │   ├── devices.py         # 台账/量测查询
│   │   ├── alarms.py          # 告警查询/分析
│   │   ├── defects.py         # 缺陷分级
│   │   ├── diagnoses.py       # 故障诊断
│   │   ├── workorders.py      # 工单
│   │   └── knowledge.py       # 知识库管理
│   ├── engine/                # Agent 引擎（自研）
│   │   ├── intent_router.py   # 意图路由
│   │   ├── react_loop.py      # ReAct 主控循环
│   │   ├── tool_dispatcher.py # 工具调度器
│   │   ├── guards.py          # 二次确认/降级/输出校验
│   │   └── tracer.py          # 追溯器
│   ├── skills/                # 业务能力（与引擎解耦）
│   │   ├── rag.py             # RAG 问答
│   │   ├── query.py           # 状态/量测/台账查询
│   │   ├── alarm.py           # 告警分析
│   │   ├── defect.py          # 缺陷分级 + 规则引擎
│   │   ├── diagnosis.py       # 故障诊断（调用技能包）
│   │   └── workorder.py       # 工单服务
│   ├── packs/                 # 技能包
│   │   ├── base.py            # SkillPack 抽象接口
│   │   ├── switchgear/        # 开关柜
│   │   ├── transformer/       # 变压器
│   │   └── cable/             # 电缆
│   ├── data/                  # 数据层
│   │   ├── models.py          # ORM 模型（DR-001~007）
│   │   ├── repository.py      # 数据访问
│   │   ├── adapter.py         # 数据接入适配器
│   │   └── vectorstore.py     # 向量库抽象
│   └── core/                  # 通用基础设施
│       ├── auth.py            # JWT + RBAC
│       ├── errors.py          # 统一错误码
│       └── logging.py         # 结构化日志
├── rules/                     # 规则配置（数据驱动，非硬编码）
│   ├── level_mapping.yaml     # BR-001~006 等级映射
│   ├── defect_level.yaml      # 附录 A 缺陷分级规则
│   └── thresholds/            # 各技能包阈值表
├── data/                      # 模拟数据 + 生成脚本
├── eval/                      # 评估集（与训练数据隔离）
│   └── embedding/             # 向量化模型评测脚本 + 检索评测集
├── web/                       # Web Demo 前端（静态，调用 /api/v1）
├── tests/                     # 单元/集成测试
├── docker-compose.yml
├── Dockerfile
├── pyproject.toml
└── README.md
```

## 4 核心模块设计

### 4.1 Agent 引擎（自研）

引擎是平台的"大脑"，负责把用户意图编排成一次可追溯、可安全执行的工具链。引擎本身**不含任何业务逻辑**，业务逻辑全部在能力层与技能包中实现。

#### 4.1.1 意图路由 IntentRouter

对应 FR-001。采用"规则优先 + LLM 兜底"两级策略，避免把高频、确定性的意图判断也交给 LLM（省 token、降延迟、可解释）：

1. **规则层**：关键词/正则 + 实体（设备编号、量测类型、缺陷关键词）快速命中，命中即返回高置信度标签。
2. **LLM 兜底层**：规则未命中或置信度低于阈值时，用 LLM 做七分类，输出 JSON `{intent, confidence}`。
3. **澄清层**：置信度仍低于阈值 → 生成引导式澄清提问，不终止会话。

七类意图：问答、状态查询、告警分析、缺陷分级、故障诊断、工单生成、其他。

**定位说明（软先验，不锁工具）**：意图路由只做三件事——①按实体（设备类型）选择技能包；②组织系统提示词（把相关工具 schema 排前）；③低置信时澄清。它**不决定循环内能调用哪些工具**。工具全局注册，混合问题（既查 RAG 又查数据库）由 4.1.2 主循环跨步调用多个工具、最后合成，意图标签仅取"主意图"。

#### 4.1.2 ReAct 主控循环 AgentLoop

对应 FR-002。核心是**自研的状态机**，不依赖任何 agent 框架：

```
for step in 1..max_steps(6):
    action = llm(plan_prompt + history + tool_schemas)   # 推理
    if action == final_answer: break                       # 终止
    if action == tool_call:
        result = dispatcher.execute(tool_name, params)     # 行动
        history.append(observation)                        # 观察
        if guards.need_confirm(result):                    # 二次确认挂起
            return pending_confirmation(result)
        tracer.record(step, tool, result, elapsed)
else:
    return clarify("请细化问题")
```

关键控制点：

| 控制点 | 规则 |
|--------|------|
| 步数上限 | 6 步，超限输出"请细化问题" |
| 死循环检测 | 重复调用同一工具且结果无进展 → 立即终止（对应 FR-002 死循环率 0） |
| 工具超时 | 单工具执行超时 10s，不重试，回填结构化错误 |
| LLM 超时 | 30s，重试 1 次（幂等） |

LLM 输出协议（JSON，pydantic 强校验）：工具调用 `{action:"tool_call", tool:"...", params:{...}}`；最终结论 `{action:"final_answer", answer:"...", sources:[...]}`。协议非法时进入一次自纠（回填错误提示让模型重试），仍失败则终止并提示。

**多工具混合**：循环不限定"一次只能用一个能力域"，可跨步混用异构工具——先 `量测查询`（DB）拿事实，再 `RAG 检索` 拿规程，最后 `final_answer` 合成并聚合所有用到的工具来源。步数上限 6 足够覆盖"查库 + 查知识 + 合成"三步以内的混合问题。

#### 4.1.3 工具调度器 ToolDispatcher

对应 FR-003。所有工具在启动时注册进注册表，注册项含：

```
{name, schema(JSON Schema), handler, timeout, read_only, skill_pack}
```

执行流程：按 schema 校验参数（pydantic）→ 校验失败返回可读错误 → 执行 handler → 结果序列化（截断、脱敏）→ 回填对话。`read_only=False` 的写工具不直接执行，而是转交二次确认闸口。

#### 4.1.4 安全闸口 Guards

对应 FR-004、FR-052、C2、C3。三道闸口，全部在引擎层强制，业务层无法绕过：

1. **二次确认闸口**（写操作）：写工具执行前生成"操作预览"，主循环**挂起**并把预览返回用户；用户确认后才真正落库，取消则丢弃并记录。实现为会话状态机：`running → awaiting_confirm → confirmed/cancelled`。会话状态存 Redis，多实例部署下任一实例可恢复挂起中的会话。
2. **降级闸口**（诊断）：诊断工具执行前预检——量测数据是否齐备、是否超出规则适用条件（如湿度超限）；不满足则跳过确定性诊断，直接输出"建议人工复核"，不调用诊断规则。
3. **输出校验闸口**：最终结论落回前，校验"必须附来源"（问答/诊断/工单建议措施），无来源则回退为"未检索到依据 / 待人工确认"。
4. **多源校验**（混合问题）：用到哪几类能力（如 DB 查询 + RAG 检索）就须附哪几类来源，缺一类即回退。

#### 4.1.5 追溯器 Tracer

对应 FR-005、NFR-005。每个会话一条 `session` 记录，每个步骤一条 `trace` 记录：

```
{session_id, step, intent, tool, params, result, sources, elapsed_ms, degraded, created_at}
```

最终结论的 `sources` 从各步骤的 `sources` 聚合而来，保证"结论—来源"可回溯。

#### 4.1.6 记忆与多轮会话管理

平台是多轮对话（"那这台变压器呢""再出个工单"均依赖历史），采用工程标准的**三层记忆**：

| 层 | 存储内容 | 存储位置 | 生命周期 |
|----|---------|---------|---------|
| 工作记忆 | 最近 N 轮对话 + 当前 ReAct 循环中间步骤 | Redis `session:{id}:history` | 单会话，滚动窗口 |
| 会话状态 | 二次确认挂起态、当前主意图、实体锚点（设备编号/缺陷等级） | Redis `session:{id}:state` | 单会话 |
| 长期记忆 | 结构化事实（历史诊断/缺陷/工单）+ 会话摘要 | PostgreSQL（业务表 + `session_summary`） | 跨会话，持久 |

**上下文窗口管理**（防 prompt 撑爆）：

1. 滑动窗口：只带最近 K 轮（默认 8）进 prompt；
2. 摘要压缩：更早历史由 LLM 压成摘要（保留关键实体 + 结论）；
3. 实体锚点：设备编号、缺陷等级等"事实"单独存，压缩也不丢，支撑指代消解。

**长期记忆的"工具读历史"原则**：历史诊断/缺陷/工单等结构化事实存 PostgreSQL，需要时用工具查询，不塞进 prompt；会话摘要才作为轻量上下文注入。

**多轮流程**：每轮带 `session_id` → 从 Redis 取 `[摘要 + 最近 K 轮 + 实体锚点 + 挂起态]` → 拼入 prompt → 跑 ReAct → 结果写回 history 并更新锚点。二次确认的挂起-恢复即该层记忆中的一段状态；多实例下历史亦存 Redis（或 PG + Redis 热缓存），任一实例可接续会话。

### 4.2 技能包框架

对应 FR-050、NFR-007。抽象接口 `SkillPack`：

```python
class SkillPack(ABC):
    device_type: str                 # 变压器/开关柜/电缆
    def query_tools(self) -> list    # 查询工具（台账/量测/告警）
    def diagnosis_rules(self) -> list# 确定性诊断规则
    def thresholds(self) -> dict     # 阈值表
    def domain_knowledge(self) -> str# 专属知识（供 RAG 打标签）
```

技能包以目录形式组织，启动时按 `device_type` 扫描注册。新增设备类型只新增一个包，不改引擎与数据模型（NFR-007）。本期交付 3 个包：switchgear-pack、transformer-pack、cable-pack（对应 SRS 附录 B）。

### 4.3 业务能力模块

与引擎解耦，每个能力以"工具"形式暴露给调度器调用。

| 模块 | 对应需求 | 核心实现要点 |
|------|---------|-------------|
| RAG 问答 | FR-010~012 | 向量化→检索 top-k→设备域过滤→重排→带出处生成；检索为空明确"未检索到依据" |
| 状态/量测/台账查询 | FR-020~022 | 直接查 PostgreSQL；量测含实时值 + 历史序列 + 阈值对照；状态评价走规则 |
| 告警分析 | FR-030~032 | 告警查询 + 等级判定（规则）+ 处置建议（预案 + LLM 解释，附依据） |
| 缺陷分级 | FR-040~042 | 规则引擎判定等级 → 映射时限 → 超时隐患督办 |
| 故障诊断 | FR-050~052 | 调技能包诊断规则（确定性），输出故障类型 + 置信度 + 数据依据；不足则降级 |
| 工单服务 | FR-060~062 | 草稿生成（建议措施附来源）→ 二次确认 → 落库 → 关联缺陷 → 验收流转 |

### 4.4 规则引擎 RuleEngine

对应 BR-001~006、FR-031/040/041。**所有确定性计算集中于此，规则以 YAML 数据配置而非代码硬编码**，便于电力专家审改。

| 规则文件 | 承载内容 | 对应 |
|---------|---------|------|
| level_mapping.yaml | 四套等级 + 告警/状态→缺陷映射 + 冲突裁决（取高）+ 时限映射 | BR-001~006 |
| defect_level.yaml | 附录 A 缺陷三级定义与判定条件 | FR-040 |
| thresholds/ | 各技能包的量测阈值表（越限判定） | FR-031/051 |

规则引擎接口：`evaluate(rule_id, facts) -> {level, reasons, degraded}`。冲突时**取最高等级（从严）**，禁止自动降级（BR-006）。

## 5 数据模型落地（PostgreSQL）

表结构与 SRS 数据字典 DR-001~007 一一对应，字段类型按试点级标准落到 PostgreSQL。

### 5.1 业务表

| 表 | 对应 DR | 关键字段 | 索引/约束 |
|----|--------|---------|----------|
| device | DR-001 | device_id(PK), device_type, voltage_level, status | device_type 索引 |
| measure_point | DR-002 | point_id(PK), device_id(FK), measure_type, threshold_upper/lower, latest_value | (device_id, measure_type) 索引 |
| measure_value | DR-003 | value_id(PK), point_id(FK), ts, value, quality | (point_id, ts) 复合索引，按月分区 |
| defect | DR-004 | defect_id(PK), device_id(FK), level, deadline, status | level、status 索引 |
| alarm | DR-005 | alarm_id(PK), device_id(FK), alarm_type, level, status | level、trigger_time 索引 |
| work_order | DR-006 | order_id(PK), ref_type, ref_id, level, status, confirm_user | (ref_type, ref_id) 索引 |
| knowledge_doc | DR-007 | doc_id(PK), doc_type, device_domain, vector_id | device_domain 索引 |

### 5.2 引擎支撑表（SRS 追溯需求落地）

| 表 | 用途 | 关键字段 |
|----|------|---------|
| app_user | RBAC 鉴权 | user_id, username, role, password_hash |
| session | 会话级追溯 | session_id, user_id, intent, created_at |
| trace | 步骤级追溯 | trace_id, session_id, step, tool, params, result, sources, elapsed_ms, degraded |
| message | 会话历史（多轮持久化） | message_id, session_id, role, content, created_at |
| session_summary | 会话摘要（压缩窗口外历史） | session_id, summary, anchors, updated_at |

> Redis 键约定：`session:{id}:history`（工作记忆）、`session:{id}:state`（挂起态）、`session:{id}:anchors`（实体锚点）。

### 5.3 时序与向量数据

- **时序**：`measure_value` 按 `(point_id, ts)` 建复合索引，试点期按月分区；若数据量增长，可平滑迁移 TimescaleDB（超表），不改变查询接口。
- **向量**：知识切片向量存 ChromaDB，`knowledge_doc.vector_id` 关联；`vectorstore.py` 抽象接口，预留 FAISS 实现。
- **语料版本治理**：每个切片携带 front matter 元数据（`status` / `superseded_by` / `effective_date` / `source`）；检索默认过滤 `status=superseded` 的旧版语料（旧版保留在库中供审计/追溯，但不参与检索）。`superseded_by` 建立新旧版本链，答案引用须带版本号与状态，杜绝"新旧标准冲突"（见 ADR-011）。

### 5.4 数据接入适配器

对应 IF-001。外部数据（CSV/JSON）经适配器归一化为内部模型后写入业务表；预留 PMS/监测系统适配器接口，本期以模拟数据验证。

### 5.5 向量化模型选型与评测

选型原则：使用**通用嵌入模型**（非领域微调），从多个候选模型中评测择优，不绑定单一模型。

**候选模型池（≥3 个对比）**：

| 模型 | 类型 | 维度 | 说明 |
|------|------|------|------|
| OpenAI text-embedding-3-small / large | 云端 API | 1536 / 3072 | 通用性强，按 token 计费 |
| bge-m3 | 本地/开源 | 1024 | 多语言，中文好，可离线 |
| bge-large-zh-v1.5 | 本地/开源 | 1024 | 中文专用，可离线 |
| m3e-base | 本地/开源 | 768 | 中文，轻量 |

**评测方法**：构建检索评测集（≥100 个"问题 → 应命中文档"对，取自知识库规程/案例），每个候选模型分别向量化入库 + 检索，测以下指标：

| 指标 | 定义 |
|------|------|
| Recall@5 / Recall@10 | 前 5 / 10 个召回结果中命中应命中文档的比例 |
| MRR | 首个命中结果排名的倒数均值 |
| 命中率 | 前 10 个结果中至少命中一次的比例 |

**选优标准**：以 Recall@k 与 MRR 为准，结合**延迟**与**成本**（云端按 token 计费）综合评分，最高者中标并写入《评估报告》。切换模型只改配置，不改业务代码（`vectorstore.py` embedding 抽象）。

**交付物**：`eval/embedding/` 下提供评测脚本 + 检索评测集，评测结果随评估报告提交。

---

## 6 接口设计（REST）

对应 IF-004。统一前缀 `/api/v1`。

### 6.1 接口清单

| 方法 | 路径 | 说明 | 权限 | 写/读 |
|------|------|------|------|-------|
| GET | /api/v1/health | 健康检查（负载均衡探活） | 公开 | 读 |
| POST | /api/v1/chat | 对话入口（意图→编排→结论） | 全部角色 | 混合 |
| GET | /api/v1/devices/{id} | 台账查询 | 全部 | 读 |
| GET | /api/v1/devices/{id}/measurements | 量测查询（实时+历史） | 全部 | 读 |
| GET | /api/v1/alarms | 告警查询 | 全部 | 读 |
| POST | /api/v1/alarms/{id}/analysis | 告警等级判定 + 处置建议 | 全部 | 读 |
| POST | /api/v1/defects/evaluate | 缺陷等级判定 | 全部 | 读 |
| POST | /api/v1/diagnoses | 故障诊断 | 全部 | 读 |
| POST | /api/v1/workorders | 生成工单草稿 | 全部 | 写（草稿） |
| PUT | /api/v1/workorders/{id}/confirm | 工单二次确认 | 全部（二次确认） | 写 |
| PUT | /api/v1/workorders/{id}/accept | 工单验收 | 计划/管理、管理员 | 写 |
| POST | /api/v1/knowledge | 知识入库 | 管理员 | 写 |
| GET | /api/v1/knowledge/search | 知识检索 | 全部 | 读 |
| GET | /api/v1/traces/{session_id} | 追溯查询 | 管理员 | 读 |

### 6.2 统一返回与错误码

成功：`{code:0, message:"ok", data:{...}}`；失败：`{code:非0, message:"错误说明", data:null}`。

| code | 含义 |
|------|------|
| 0 | 成功 |
| 400 | 参数错误 |
| 401 | 未认证 |
| 403 | 无权限 |
| 404 | 资源不存在 |
| 429 | 限流 |
| 500 | 内部错误（不向外泄露原始堆栈） |
| 504 | 上游（LLM/向量库）超时 |

### 6.3 鉴权与 RBAC 落地

- JWT（HS256），payload 含 `user_id`、`role`；`Authorization: Bearer <token>`。
- 每个接口在装饰器层声明所需操作权限，按第 8 章权限矩阵校验；写接口在服务端**二次校验**（前端隐藏仅作体验）。
- 限流：读接口 60 次/分钟/用户，写接口 10 次/分钟/用户（429）。

## 7 关键流程时序

### 7.1 故障诊断 → 工单（含二次确认）

覆盖 FR-002/003/004、FR-051/052、FR-060/061。核心是"写操作在主循环内挂起等待确认"。

```mermaid
sequenceDiagram
    participant U as 用户
    participant API as FastAPI
    participant IR as 意图路由
    participant LP as ReAct循环
    participant TD as 工具调度
    participant G as 安全闸口
    participant DIAG as 诊断技能包
    participant PG as PostgreSQL

    U->>API: 自然语言：变压器局放异常，帮我出工单
    API->>IR: 意图分类
    IR-->>API: 故障诊断 + 工单生成
    API->>LP: 启动主循环
    LP->>TD: 调用诊断工具(设备+量测)
    TD->>G: 降级闸口预检
    alt 数据不足/超适用条件
        G-->>LP: 降级：建议人工复核（附原因）
    else 条件满足
        G->>DIAG: 执行确定性规则
        DIAG-->>G: 故障类型+置信度+数据依据
        G-->>LP: 诊断结果(附来源)
    end
    LP->>TD: 调用工单草稿工具(写)
    TD->>G: 二次确认闸口
    G-->>LP: 返回待确认预览
    LP-->>U: 请求确认：预览工单草稿
    U->>LP: 确认
    LP->>TD: 落库(已确认)
    TD->>PG: 写入 work_order
    PG-->>LP: 成功
    LP-->>U: 最终结论 + 来源 + 工单号
```

### 7.2 RAG 问答（带出处）

覆盖 FR-010/011。检索为空时明确"未检索到依据"，不编造。

```mermaid
sequenceDiagram
    participant U as 用户
    participant RAG as RAG问答
    participant VEC as ChromaDB
    participant LLM as LLM
    participant TR as 追溯器

    U->>RAG: 问题
    RAG->>VEC: 向量化 + 检索 top-k
    VEC-->>RAG: 候选片段(含来源)
    alt 无相关片段
        RAG-->>U: "未检索到依据"
    else 有片段
        RAG->>LLM: 基于片段生成 + 附出处
        LLM-->>RAG: 答案+引用
        RAG->>TR: 记录 sources
        RAG-->>U: 答案（附出处）
    end
```

---

## 8 安全设计

对应 NFR-004~006、第 8 章权限矩阵。

### 8.1 鉴权与 RBAC

JWT（HS256）签发，`role` 四值：`operator`（运维）、`monitor`（值班/监控）、`manager`（计划/管理）、`admin`（系统管理员）。接口装饰器按权限矩阵校验，写接口服务端二次校验。

### 8.2 写操作二次确认

所有写操作（工单落库、知识入库、验收）统一走 4.1.4 的二次确认闸口；管理员**不豁免**业务写操作（对齐 C2 与权限矩阵说明）。确认信息落库（`confirm_user`、`confirm_time`）。

### 8.3 降级与防幻觉

- 诊断、分级走确定性规则，LLM 不参与数值判定（C1）。
- 数据不足/超适用条件 → 强制降级"建议人工复核"（C3，FR-052）。
- 问答/诊断/工单建议措施必须附来源，无来源回退为"未检索到依据/待人工确认"（FR-011/060）。

### 8.4 审计与可追溯

- 每次写操作记录：用户、时间、动作、对象、结果（审计）。
- `session`/`trace` 表留存完整调用链、来源、耗时、降级标记（FR-005）。
- 原始异常不外泄，统一映射为结构化错误码（FR-003、NFR-006）。

### 8.5 数据库只读保护

`read_only` 工具标记是应用层约定，真正的只读保证靠数据库权限（防御纵深）：

| 层 | 机制 |
|----|------|
| 应用层 | 工具 `read_only` 标记 + 调度器拦截写工具 |
| 连接层 | 三引擎分离：管理 / 只读 / 读写；查询走 `get_read_session()`，写走 `get_write_session()` |
| 数据库层 | `gridops_reader` 仅 `SELECT` 权限；`gridops_writer` 才有 DML |
| 事务层 | `gridops_reader` 设 `default_transaction_read_only = on`，任何写操作在事务层被拒 |

由 `init_roles()` 建角色并授权（见 database.py）。即使查询代码被写错/注入，数据库也会权限拒绝写操作。

---

## 9 非功能设计

| 类别 | 设计手段 | 达标措施 |
|------|---------|---------|
| 性能 NFR-001 | 规则路径直查 PostgreSQL（<500ms）；LLM 路径限步数+限 token；检索走向量索引（<2s） | 意图路由规则优先，减少 LLM 调用 |
| 容量 NFR-002 | `measure_value` 分表/分区 + 复合索引；模拟数据生成脚本支撑规模压测 | ≥1000 设备、100 万量测、10 万告警 |
| 可用性 NFR-003 | uvicorn 多 worker + 健康检查 + 优雅降级 | 试点可用性 ≥99% |
| 安全 NFR-004 | 见第 8 章 | 写确认覆盖率 100% |
| 可追溯 NFR-005 | Tracer 全量落库 | 覆盖率 100% |
| 可靠 NFR-006 | 降级闸口 + 错误映射 | 降级率 100%、报错不外泄 |
| 可扩展 NFR-007 | 技能包 + 适配器抽象 | 新场景只加包 |
| 可维护 NFR-008 | 分层解耦 + 规则配置化 + 结构化日志 | 关键模块单测 ≥70% |
| 兼容 NFR-009 | LLM/向量库/库均接口抽象 | 可替换 |

## 10 部署方案（试点级）

### 10.1 拓扑

多实例试点部署，容器：`api`（FastAPI + uvicorn，可水平扩展 ×N）、`postgres`（结构化）、`chromadb`（向量）、`redis`（会话状态）、`web`（前端静态 Demo）。LLM 为外部 OpenAI 兼容服务（DeepSeek），通过配置指向。会话状态外置 Redis，保证多实例下二次确认挂起态可恢复。

### 10.2 docker-compose（示意）

```yaml
services:
  api:
    build: .
    ports: ["8000:8000"]
    environment:
      - DATABASE_URL=postgresql+psycopg://app:${PG_PASSWORD}@postgres:5432/gridops
      - CHROMA_HOST=chromadb
      - REDIS_URL=redis://redis:6379/0
      - LLM_BASE_URL=${LLM_BASE_URL}
      - LLM_API_KEY=${LLM_API_KEY}
      - JWT_SECRET=${JWT_SECRET}
    depends_on: [postgres, chromadb, redis]
    deploy:
      replicas: 2
  web:
    image: nginx:alpine
    ports: ["8080:80"]
    volumes: [../web:/usr/share/nginx/html:ro]
    depends_on: [api]
  postgres:
    image: postgres:16
    environment: [POSTGRES_PASSWORD=${PG_PASSWORD}]
    volumes: [pgdata:/var/lib/postgresql/data]
  chromadb:
    image: chromadb/chroma
    volumes: [chromadata:/chroma/chroma]
  redis:
    image: redis:7-alpine
    volumes: [redisdata:/data]
volumes:
  pgdata:
  chromadata:
  redisdata:
```

### 10.3 配置项（环境变量）

| 配置 | 说明 | 默认 |
|------|------|------|
| DATABASE_URL | PostgreSQL 管理连接串（建表/建角色） | — |
| DATABASE_URL_READ / DATABASE_URL_WRITE | 只读/读写连接串（角色分离，见 8.5） | gridops_reader / gridops_writer |
| CHROMA_HOST / CHROMA_PORT | 向量库地址 | chromadb:8000 |
| LLM_BASE_URL / LLM_API_KEY / LLM_MODEL | OpenAI 兼容 LLM | DeepSeek |
| JWT_SECRET / JWT_EXPIRE_MINUTES | 鉴权 | — / 480 |
| REDIS_URL | 会话状态 Redis | redis://redis:6379/0 |
| EMBEDDING_MODEL | 向量化模型（评测中标者） | 见 5.5 |
| MAX_STEPS | ReAct 步数上限 | 6 |
| TOOL_TIMEOUT / LLM_TIMEOUT | 超时 | 10s / 30s |
| RATE_LIMIT_READ / RATE_LIMIT_WRITE | 限流 | 60 / 10 次/分钟 |

---

## 11 关键设计决策（ADR）

| 编号 | 决策 | 理由 | 代价/替代 |
|------|------|------|----------|
| ADR-001 | 自研 ReAct，不引入 LangChain/LlamaIndex | C1/C2/C3 安全闸口与追溯需完全掌控；框架抽象层增加调试成本；"通用引擎"定位 | 需自行维护主循环与输出解析 |
| ADR-002 | 确定性计算全部走规则引擎，LLM 只编排 | C1，防幻觉 | 规则维护成本，需电力专家审改 |
| ADR-003 | 时序数据独立 `measure_value` 分表 | 支撑百万级记录与 <500ms 查询（NFR-001/002） | 引入分区/索引管理 |
| ADR-004 | 试点级 PostgreSQL + ChromaDB | 用户选定；生产试点标准 | 运维成本高于 SQLite 单机 |
| ADR-005 | 二次确认实现为主循环"挂起-恢复"状态 | 写操作与对话流天然耦合，需用户就地确认 | 会话状态需外置 Redis |
| ADR-006 | 意图路由"规则优先 + LLM 兜底" | 高频确定意图省 token、降延迟、可解释 | 规则需覆盖常见表达 |
| ADR-007 | 向量化模型多候选评测选优（通用嵌入） | 不绑定单一模型，按准确率/延迟/成本择优 | 需维护评测集与脚本 |
| ADR-008 | 前端用静态 Web Demo，前后端分离 | 演示交付简单，后端解耦 | 生产 UI 后续另做 |
| ADR-009 | 会话状态外置 Redis，api 多实例部署 | 多实例下二次确认挂起态可恢复 | 引入 Redis 运维 |
| ADR-010 | 数据库只读角色分离（reader 仅 SELECT + 事务只读） | 只读保护不能只靠代码标记，需 DB 权限兜底 | 引入建角色/授权步骤 |
| ADR-011 | RAG 语料版本治理（status/superseded_by 元数据 + 检索过滤） | 规程会更新，新旧并存会导致检索到过时规则 | 需维护版本元数据 |

---

## 12 风险与遗留问题

| 风险/遗留 | 影响 | 应对 |
|----------|------|------|
| LLM 输出协议不稳定 | 主循环中断 | 强 schema 校验 + 一次自纠 + 超限终止 |
| 模拟数据与真实差异 | 结论代表性 | 适配器预留真实接口，明确标注数据性质 |
| 时序数据增长 | 查询变慢 | 分区 + 预留 TimescaleDB 迁移路径 |
| 规则阈值需专家校准 | 分级/诊断准确性 | 规则 YAML 化，随评估报告迭代 |
| 向量化模型效果不确定性 | 检索准确率不达标 | 多候选评测选优（5.5），评估报告兜底 |

**已确认事项**（原遗留待定项，v0.2 关闭）：

1. 向量化模型：通用嵌入，多候选评测选优（见 5.5）。
2. 前端：静态 Web Demo，前后端分离（见 2.1 / 10）。
3. 会话状态：Redis 外置，api 多实例部署（见 ADR-009）。

---

*本文档与 SRS-GRID-OPS-AGENT v1.2 配套；详细设计（类图、接口字段级定义、DDL）在评审通过后展开。*
