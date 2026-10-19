# 电网智能运维助手 Agent 平台（grid-ops-agent）

面向电网设备运维场景的智能助手 Agent 平台。核心思路：**框架通用、场景插件化，LLM 只负责编排与解释，确定性计算（缺陷分级、故障诊断、设备映射）全部由可审改的规则引擎完成**，从而把「安全」和「成本」两条线都压到极致。

> 一句话定位：一个「信规则、不靠模型拍脑袋」的运维 Agent —— 该答的答、该反问的反问、该降级人工的降级，写操作永远过二次确认闸口。

---

## 为什么是它（核心设计理念）

1. **LLM 仅编排，确定性计算走规则（C1）**
   缺陷分级、故障诊断、阈值映射等数值判定走 YAML 规则引擎，LLM 不参与数值结论，天然规避「模型编造等级」的问题。

2. **写操作二次确认（C2）**
   生成工单等写操作先出「草稿预览」，确认后才真正落库；安全不依赖模型「听话」，而依赖二次确认闸口 + 幂等键 + 数据库只读角色。

3. **数据不足降级、不编造（C3）**
   知识库外的问题诚实回答「不知道」；危急缺陷若判定依据不足，降级为「人工复核」而不是默认放行；回答附出处，幻觉可溯源。

4. **极致成本与延迟**
   实测单问 LLM 成本约 ¥0.0008、稳态端到端约 3 秒。

5. **无框架绑架的轻量自研 ReAct**
   不依赖 LangChain，自研 ReAct 循环 + 工具调度 + 安全闸口，架构干净、可控。

---

## 架构总览

```
┌─────────────────────────────────────────────────────────────┐
│                        接入层 / API                          │
│   FastAPI（REST + SSE 流式）+ MCP Server（SSE，/mcp）          │
└──────────────────────────────┬──────────────────────────────┘
                               │
┌──────────────────────────────▼──────────────────────────────┐
│                      Agent 引擎（app/engine）                 │
│  意图路由 → ReAct 循环 → 工具调度 → 闸口 → 追溯 → 记忆          │
│  + 证据账本（溯源）+ 预算账本（限额）+ 检查点（中断恢复）          │
└───────────────┬──────────────────────────────┬──────────────┘
                │                              │
┌───────────────▼───────────────┐  ┌───────────▼───────────────┐
│     能力层（app/skills）        │  │   领域插件（app/packs）      │
│  问答(RAG)/查询/告警/缺陷/       │  │  开关柜 switchgear          │
│  诊断/工单/复盘案例             │  │  变压器 transformer         │
└───────────────┬───────────────┘  │  电缆 cable                │
                │                  └───────────┬───────────────┘
┌───────────────▼──────────────────────────────▼──────────────┐
│     确定性规则引擎（rules/*.yaml）+ 工具层（只读/读写分离）        │
│   defect_level / level_mapping / thresholds/{设备}             │
│   + 结构化缺陷库 defect_library（5964 条）                      │
└───────────────┬──────────────────────────────┬──────────────┘
                │                              │
┌───────────────▼───────────────┐  ┌───────────▼───────────────┐
│        数据层                   │  │      外部大模型             │
│  PostgreSQL + ChromaDB + Redis │  │  DeepSeek（OpenAI 兼容）    │
└───────────────────────────────┘  └───────────────────────────┘
```

**分层职责**

| 层 | 目录 | 说明 |
|----|------|------|
| 接入层 | `app/api/`、`app/main.py` | REST 接口、SSE 流式、MCP 服务器挂载 |
| Agent 引擎 | `app/engine/` | 意图路由、ReAct 循环、工具调度、安全闸口、证据溯源、预算、检查点、多轮记忆 |
| 能力层 | `app/skills/` | 问答(RAG)、设备查询、告警分析、缺陷分级、故障诊断、工单、复盘案例 |
| 领域插件 | `app/packs/` | 可插拔技能包：开关柜 / 变压器 / 电缆 |
| 确定性规则 | `rules/` | 缺陷分级关键词、等级映射、各设备阈值、结构化缺陷库（YAML，可审改） |
| 数据层 | `app/data/` | PostgreSQL（ORM/仓储）、ChromaDB（向量）、Redis（实时） |

---

## 技术栈

| 类别 | 选型 |
|------|------|
| 语言 | Python ≥ 3.10 |
| Web 框架 | FastAPI + Uvicorn + Pydantic v2 |
| 数据 | PostgreSQL 16（SQLAlchemy）、ChromaDB、Redis 7 |
| LLM | DeepSeek（`deepseek-chat`，OpenAI 兼容协议） |
| 嵌入模型 | `BAAI/bge-small-zh-v1.5`（6 模型对比后选定：越小越准） |
| 检索 | 混合检索（向量 + 关键词 bigram，RRF）+ rerank 精排（`bge-reranker-base`） |
| 鉴权 | JWT（python-jose） |
| OCR | 本地 PaddleOCR（正文）+ 百度表格识别（复杂表格） |
| 测试 | pytest（105 个单测，纯逻辑不依赖 DB/LLM） |

---

## 知识库（三层语料）

知识库不是单一来源，而是三层结构：

| 层 | 位置 | 内容 | 规模 |
|----|------|------|------|
| 基础规程 | `data/docs/`（已提交） | 34 篇电力规程摘编（含版本治理 front matter） | 34 篇 |
| 企业级标准/导则/案例 | `资料/`（仓库外，版权不提交） | 国网/行标/企标：Q/GDW 745/1906、DL/T 系列、状态评价/检修导则、安规、故障案例汇编 | 101 文件（1.1GB） |
| 结构化缺陷库 | `rules/defect_library*.yaml`（已提交，派生数据） | 从 Q/GDW 745（配电网）+ 1906（输变电）抽取的设备×部件×部位×缺陷×等级×分类依据 | 5964 条 |

> 原始标准资料（`资料/` 的 PDF/OCR）因版权**不提交仓库**；结构化缺陷库为派生数据已提交，标准更新时可用 `scripts/gen_defect_library.py` 重建。

**知识库构建流程**（离线一次）：

```
101 PDF ──OCR(本地 PaddleOCR + 百度表格)──清洗(去广告/水印/乱码)──结构切分──向量化(bge-small)──ChromaDB（7107 chunk）
```

**在线检索链路**（每次问答）：

```
问题 ──混合召回(向量+关键词 RRF, top-30)──rerank 精排(top-5)──LLM 生成带出处答案
```

**缺陷定级链路**（确定性，LLM 不参与）：

```
缺陷描述 ──关键词规则──缺陷库匹配(bigram 字面)──设备域筛选──单一等级命中才定级 / 歧义降级人工复核
```

详见 [`docs/RAG检索技术说明.md`](docs/RAG检索技术说明.md)。

---

## 目录结构

```
grid-ops-agent/
├── app/
│   ├── main.py            # FastAPI 入口 + 路由注册 + MCP 挂载
│   ├── config.py          # 配置（pydantic-settings，读 .env）
│   ├── mcp_server.py      # MCP 服务器（SSE）
│   ├── api/               # 接口层（health/auth/chat/devices/alarms/defects/diagnoses/workorders/
│   │                      #         sessions/knowledge/tools/traces/messages/review_cases/metrics/evals）
│   ├── engine/            # Agent 引擎（react_loop/intent_router/rule_engine/tool_dispatcher/
│   │                      #          guards/tracer/memory/llm/evidence/budget/checkpoint）
│   ├── skills/            # 能力层（rag/query/alarm/defect/diagnosis/workorder/review_case）
│   ├── packs/             # 领域插件（switchgear/transformer/cable）
│   ├── data/              # 数据层（models/repository/database/source/vectorstore/kb/ingest/
│   │                      #          ocr_clean/retrieval/rerank/defect_lib/defect_embeddings）
│   └── core/              # 认证、错误码、日志
├── rules/                 # 确定性规则（defect_level/level_mapping/thresholds/*/defect_library）
├── data/
│   ├── docs/              # 基础语料（34 篇电力规程摘编，含版本治理）
│   └── generate_mock.py   # 模拟数据生成
├── tests/                 # 回归测试（105 个单测，纯逻辑不依赖 DB/LLM）
├── eval/                  # 评估（qa_set/qa_generated + Recall@K 评测 + 定级压测 + 报告）
├── scripts/               # 数据/知识库脚本（OCR/清洗/切分/入库/缺陷库生成/一致性自检/归档/评测结果固化）
├── web/                   # 前端 Demo（单页；工作台重写设计见 docs/前端工作台设计.md）
├── docs/                  # SRS/SDD + RAG技术说明 + Agent引擎增强总结 + 切分踩坑记录 + 前端工作台设计
├── docker-compose.yml
├── Dockerfile
├── pyproject.toml
└── README.md
```

---

## 快速开始

### 方式一：Docker（推荐，一键起全栈）

```bash
docker compose up --build
```

启动后：

| 服务 | 地址 |
|------|------|
| API 健康检查 | http://localhost:8000/api/v1/health |
| Swagger 接口文档 | http://localhost:8000/docs |
| 前端 Demo | `web/index.html`（直接用浏览器打开） |
| MCP 端点（SSE） | http://localhost:8000/mcp/sse |

### 方式二：本地开发（自己的 Python 环境）

```bash
pip install -e ".[dev]"
cp .env.example .env   # 填 LLM_API_KEY 等
python -m uvicorn app.main:app --reload   # 务必用 python -m，避免 PATH 解析错
```

---

## 配置说明（`.env`）

| 变量 | 说明 | 默认 |
|------|------|------|
| `LLM_BASE_URL` / `LLM_API_KEY` / `LLM_MODEL` | LLM 接口（OpenAI 兼容） | deepseek-chat |
| `EMBEDDING_MODEL` | 嵌入模型 | `BAAI/bge-small-zh-v1.5` |
| `CHROMA_HOST` / `CHROMA_PORT` | 向量库地址 | localhost / 8000 |
| `JWT_SECRET` | 鉴权密钥（**生产必须改**） | change-me |
| `PG_PASSWORD` | PostgreSQL 密码 | app |

> `.env` 已被 `.gitignore` 排除，请勿提交真实 API Key。

---

## 初始化数据与知识库

```bash
# 1. 建表 + 建数据库角色 + 幂等迁移（补列/补索引）
python -m app.data.database

# 2. 初始化演示用户（admin/operator/monitor/manager）
python scripts/init_users.py

# 3. 生成模拟设备/告警数据
python data/generate_mock.py --scale demo

# 4. 基础语料入库（34 篇规程 → ChromaDB）
python scripts/ingest_kb.py

# 5. （可选）企业级语料入库：先把标准 PDF 放资料/ 目录，OCR 扫描件后入库
python scripts/ocr_pdfs.py        # OCR 扫描件 → 资料/ocr_text/
python scripts/ingest_ocr_kb.py   # 清洗 + 切分 + 入库

# 6. （可选）生成结构化缺陷库（需自备 Q/GDW 745/1906 标准资料）
python scripts/gen_defect_library.py
```

---

## 测试

```bash
python -m pytest tests/
```

> 105 个单测（纯逻辑不依赖 DB/LLM/Redis），覆盖规则引擎、工具、清洗、切分、检索、缺陷库抽取、证据/预算、数据源适配器、工单确认、评估结果固化。

---

## API 概览

统一返回结构 `{ "code": 0, "message": "ok", "data": {...} }`；除 `/health`、`/auth/login` 外均需 `Authorization: Bearer <token>`。

| 模块 | 端点（部分） |
|------|-------------|
| 鉴权 | `POST /auth/login` |
| 对话 | `POST /chat`、`POST /chat/stream`（SSE） |
| 设备 | `GET /devices`、`GET /devices/{id}/overview`、`/measurements`、`/state` |
| 告警 | `GET /alarms`、`POST /alarms/analyze` |
| 缺陷 | `GET /defects`、`POST /defects/evaluate`、`GET /defects/deadline/{level}` |
| 诊断 | `POST /diagnoses` |
| 工单 | `GET /workorders`、`POST /workorders`（落库草稿）、`POST /workorders/draft`、`POST /workorders/{id}/confirm\|cancel` |
| 知识 | `GET /knowledge/docs`、`POST /knowledge/ingest`、`GET /knowledge/search` |
| 复盘案例 | `GET /review-cases`、`/search`、`POST /review-cases/{id}/approve\|reject\|supersede` |
| 历史消息 | `GET /messages`（按会话/时间/分页） |
| 会话 | `GET /sessions` |
| 工具 | `GET /tools` |
| 追溯 | `GET /traces/{session_id}` |
| 可观测 | `GET /metrics`（admin） |
| 评估 | `GET /evals/summary`、`GET /evals/runs`（admin） |

完整接口见 [`API接口文档.md`](API接口文档.md)、[`前端接口文档.md`](前端接口文档.md)。

**默认演示账号**：admin / admin123、operator / operator123、monitor / monitor123、manager / manager123。

---

## 评估结果（试点阶段）

> ⚠️ 试点阶段数字。缺陷分级的误判已压到 0，但命中率与意图识别样本量仍未达 SRS 正式验收规模，详见下方口径说明。

| 维度 | 结果 | 目标 | 状态 |
|------|------|------|------|
| 缺陷分级（闭卷，缺陷库 5964 条黄金标注对拍） | 误判 **0**（0.0%）；命中 31.5%（带设备域）/ 22.2%（不带）；其余降级交人工 | 误判≈0 | ✅ 误判达标，命中率待提 |
| 意图识别（规则层） | 11/12 = 91.7%（样本仅 12 条） | ≥90%（需 ≥700 样本） | ⚠️ 样本不足 |
| 知识检索 Recall@5 | 89.7%（混合检索 + rerank，300 题生成集） | ≥85% | ✅ |
| LLM 成本 | ≈ ¥0.0008 / 问 | 可忽略 | ✅ |
| 稳态端到端延迟 | ≈ 3.0s / 问 | <15s | ✅ |

**缺陷分级口径**：`命中率`是「自动化覆盖率」（多少缺陷能自动定级），`误判率`是安全红线（定错等级最危险）。2026-10 已收紧关键词规则（去掉「明显/破损/超标/发热/沉降/爬电/放电/击穿」等宽泛词，仅保留精确率 100% 的词），误判压到 0；命中率 31.5% 的瓶颈是 bigram 字面匹配扛不住口语化表述，需「口语化输入归一化」提升。复现：`python scripts/eval_defect_grading_closed.py`。

**意图识别口径**：仅 12 条规则层样本，SRS 验收需 ≥700 且含 LLM 兜底层，当前样本量远未达标。

---

## 文档索引

| 文档 | 说明 |
|------|------|
| [`docs/RAG检索技术说明.md`](docs/RAG检索技术说明.md) | 知识库构建 + 检索技术全貌（含指标） |
| [`docs/Agent引擎增强总结.md`](docs/Agent引擎增强总结.md) | M7 引擎增强（证据/预算/中断恢复/案例库） |
| [`docs/前端工作台设计.md`](docs/前端工作台设计.md) | 前端工作台设计说明（React+TS+Vite，页面清单与后端接口对齐） |
| [`docs/知识库切分踩坑记录.md`](docs/知识库切分踩坑记录.md) | OCR 清洗与切分踩坑（6 个坑） |
| [`docs/历史数据保留与复盘案例库设计.md`](docs/历史数据保留与复盘案例库设计.md) | 历史保留 + 案例库设计 |
| [`docs/电网智能运维助手Agent平台_软件需求规格说明书SRS.md`](docs/电网智能运维助手Agent平台_软件需求规格说明书SRS.md) | 需求规格说明书 |
| [`docs/电网智能运维助手Agent平台_系统设计说明书.md`](docs/电网智能运维助手Agent平台_系统设计说明书.md) | 系统设计说明书 |
| [`API接口文档.md`](API接口文档.md) / [`前端接口文档.md`](前端接口文档.md) | 接口对接 |
| [`eval/评估报告.md`](eval/评估报告.md) | 试点阶段评估报告 |

---

## 里程碑

- [x] M0 工程骨架
- [x] M1 数据层（三角色分离）
- [x] M2 规则引擎 + 技能包
- [x] M3 工具层
- [x] M4 Agent 引擎（意图路由 / ReAct / 二次确认 / 幻觉溯源）
- [x] M5 接口 + 前端 Demo + MCP
- [x] M6 评估 + 报告
- [x] M7 引擎增强（证据溯源 / 预算账本 / 中断恢复 / 会话历史持久化 / 复盘案例库 / 工单确定性快路径）
- [x] 知识库构建线（OCR → 清洗 → 结构切分 → 混合检索 + rerank → 结构化缺陷库）
- [x] 落地准备（Agent 可观测/监控、真实数据接入适配器框架、前端工作台设计、工单确认/评估看板后端补全）

---

## 已知限制与路线图

- 评估样本量尚未达到正式验收规模（缺陷 ≥200、意图 ≥700），当前为试点阶段结论。
- 双重否定、边缘口语表述依赖「降级人工复核」兜底（口语化输入归一化待做）。
- 写操作目前仅「工单草稿落库」，尚未接入真实 SSH / K8s 等执行闭环。
- RBAC 多租户与审计仍未做；前端工作台设计已产出（React+TS+Vite，见 `docs/前端工作台设计.md`），实现未开始。
- 原始标准资料（`资料/` 的 PDF/OCR）因版权不提交仓库；结构化缺陷库已提交，标准更新时可用 `scripts/gen_defect_library.py` 重建。

---

## 许可证

本项目采用 [MIT License](LICENSE) 开源协议。Copyright (c) 2026 grid-ops-agent contributors。
