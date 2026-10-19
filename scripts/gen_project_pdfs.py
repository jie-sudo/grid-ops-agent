"""生成三份项目 PDF：差距待办、技术知识点全解、完整项目文档。

用法：python scripts/gen_project_pdfs.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.cidfonts import UnicodeCIDFont
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle, PageBreak

pdfmetrics.registerFont(UnicodeCIDFont("STSong-Light"))

ROOT = Path(__file__).resolve().parent.parent

H1 = ParagraphStyle("h1", fontName="STSong-Light", fontSize=20, leading=28, alignment=1, spaceAfter=4)
SUB = ParagraphStyle("sub", fontName="STSong-Light", fontSize=10, leading=14, alignment=1, textColor=colors.grey)
H2 = ParagraphStyle("h2", fontName="STSong-Light", fontSize=14, leading=20, spaceBefore=16, spaceAfter=8, textColor=colors.HexColor("#2563eb"))
H3 = ParagraphStyle("h3", fontName="STSong-Light", fontSize=12, leading=18, spaceBefore=10, spaceAfter=4)
P = ParagraphStyle("p", fontName="STSong-Light", fontSize=10.5, leading=17)
B = ParagraphStyle("b", fontName="STSong-Light", fontSize=10.5, leading=17, leftIndent=12)

TABLE_STYLE = TableStyle([
    ("FONTNAME", (0, 0), (-1, -1), "STSong-Light"),
    ("FONTSIZE", (0, 0), (-1, -1), 9.5),
    ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#2563eb")),
    ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
    ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#d9e0e7")),
    ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
    ("TOPPADDING", (0, 0), (-1, -1), 5),
    ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
])


def build_pdf(filename, story):
    doc = SimpleDocTemplate(str(ROOT / filename), pagesize=A4, topMargin=40, bottomMargin=40, leftMargin=48, rightMargin=48)
    doc.build(story)
    print(f"已生成：{filename}")


def title(text, sub):
    return [Paragraph(text, H1), Paragraph(sub, SUB), Spacer(1, 18)]


# ============================================================
# PDF 1：差距与待办
# ============================================================
def gap_pdf():
    s = title("电网智能运维 Agent 平台 · 差距与上线待办", "从「演示/试点版」到「实际可用」的差距盘点")
    s.append(Paragraph("一、上线前必须补（阻塞实际使用）", H2))
    s.append(Table([
        ["缺口", "现状", "要做的"],
        ["专业前端", "纯 HTML 控制台，能用但简陋", "外包给前端工程师，21 个接口 + API 文档已备好"],
        ["真实数据接入", "只有模拟数据", "实现 PMSSource（接口已预留，字段映射表已写好）"],
        ["缺陷库结构化", "关键词规则（简化版，覆盖不全）", "按 Q/GDW 745 建结构化缺陷库（模板见缺陷 PDF）"],
    ], style=TABLE_STYLE))
    s.append(Paragraph("二、重要增强（不阻塞，但影响完整性）", H2))
    s.append(Paragraph("1. 更多技能包：现只有开关柜/变压器/电缆 3 个，缺断路器、线路、GIS、电容器等。", P))
    s.append(Paragraph("2. 工单验收状态流转：现在只能落库，缺「处理中→已验收」的完整流转（FR-062 P1）。", P))
    s.append(Paragraph("3. 隐患督办定时任务：危急缺陷超 24h 未消缺自动标记隐患（FR-042），需定时任务。", P))
    s.append(Paragraph("4. 告警处置建议：只做了等级判定，缺「结合预案生成处置建议」（FR-032，LLM+RAG）。", P))
    s.append(Paragraph("5. 长期记忆摘要压缩：三层记忆设计了 session_summary，代码里未真正用起来（长对话会撑爆 prompt）。", P))
    s.append(Paragraph("三、锦上添花（生产化，非阻塞）", H2))
    s.append(Paragraph("HTTPS + 密钥管理；CI/CD + Alembic 数据迁移；专门日志/监控面板；token 级流式输出；MCP client（接外部工具）。", P))
    s.append(Spacer(1, 16))
    s.append(Paragraph("建议优先级：前端（外包进行中）→ 真实数据接入 → 缺陷库结构化 → 技能包扩充 → 工单闭环。", H3))
    return s


# ============================================================
# PDF 2：技术知识点全解
# ============================================================
def knowledge_pdf():
    s = title("电网智能运维 Agent 平台 · 技术知识点全解", "覆盖后端 / 前端 / 通用工程，逐个说明：语言·怎么用·解决什么·关联·归属")
    s.append(Paragraph("一、后端知识点（Python）", H2))

    def k(title_, lang, use, solve, rel, where="后端"):
        s.append(Paragraph(f"{title_}（{where}）", H3))
        s.append(Paragraph(f"<b>语言/技术</b>：{lang}", B))
        s.append(Paragraph(f"<b>怎么用</b>：{use}", B))
        s.append(Paragraph(f"<b>解决了什么</b>：{solve}", B))
        s.append(Paragraph(f"<b>关联知识点</b>：{rel}", B))

    k("FastAPI", "Python Web 框架",
      "@app.get/post 路由、Depends 依赖注入、Pydantic 请求体、StreamingResponse 做 SSE 流式、CORSMiddleware 跨域",
      "REST API 服务 + 对话流式输出 + 鉴权依赖注入",
      "Pydantic、uvicorn、asyncio、SSE")
    k("Pydantic v2", "Python 数据校验库",
      "BaseModel 定义请求体、类型校验、pydantic-settings 读环境变量",
      "接口入参校验 + 配置管理，避免脏数据进入",
      "类型注解（typing）、SettingsConfigDict")
    k("SQLAlchemy 2.0", "Python ORM",
      "DeclarativeBase + Mapped/mapped_column 定义模型、session 增删查、bulk_insert_mappings 批量插入",
      "用 Python 对象操作数据库，免手写 SQL，模型即表结构",
      "PostgreSQL、psycopg3、外键约束")
    k("PostgreSQL", "关系型数据库",
      "外键保证数据一致性、复合索引提速时序查询、GRANT SELECT 建只读角色、default_transaction_read_only 事务只读",
      "结构化数据存储 + 数据库层只读保护（写操作安全的物理兜底）",
      "SQL、psycopg3、RBAC")
    k("ChromaDB", "向量数据库",
      "collection 存向量、embedding_function 注入嵌入模型、where 过滤、delete 按 metadata 删",
      "知识库文档切片向量化 + 语义检索",
      "嵌入模型（sentence-transformers）、RAG")
    k("Redis", "内存数据库",
      "lrange/rpush/ltrim 存最近 N 轮对话、set/get 存会话状态与实体锚点、decode_responses 读字符串",
      "三层记忆（工作记忆/会话状态/锚点）+ 多实例共享会话",
      "多轮对话、指代消解")
    k("sentence-transformers + bge", "嵌入模型",
      "SentenceTransformerEmbeddingFunction 加载本地模型，HF_ENDPOINT 走镜像、HF_HUB_OFFLINE 离线读缓存",
      "中文语义向量化，支撑 RAG 检索",
      "HuggingFace、向量检索")
    k("httpx + OpenAI 兼容协议", "HTTP 客户端",
      "httpx.Client post 调 /chat/completions，解析 choices[0].message.content 和 usage",
      "调用 LLM，统计 token 用量和延迟（成本测算）",
      "DeepSeek、流式输出")
    k("ReAct 主循环", "Agent 编排模式",
      "自研状态机：推理→调工具→观察→再推理，步数上限 6、死循环检测、JSON 输出协议（tool_call/final_answer/clarify）",
      "LLM 编排多工具完成复杂任务，不依赖 LangChain 等框架",
      "工具调度、意图路由、安全闸口")
    k("规则引擎 + YAML", "确定性计算",
      "YAML 配置分级关键词/等级映射，RuleEngine 加载并 evaluate",
      "缺陷分级/时限/等级映射走确定性规则，LLM 不参与数值判定（防幻觉）",
      "Q/GDW 745、降级人工复核")
    k("技能包（可插拔）", "架构模式",
      "BaseSkillPack 抽象基类 + 每设备类型一个子类，启动时按 device_type 注册",
      "新增设备类型只加一个包，不改引擎（可扩展性）",
      "抽象基类（ABC）、注册表")
    k("JWT + PBKDF2", "认证",
      "python-jose 签发/校验 JWT（HS256），hashlib.pbkdf2_hmac 哈希密码（避开 passlib/bcrypt 版本坑）",
      "登录鉴权 + 多用户会话归属",
      "RBAC、HTTPBearer")
    k("RBAC", "权限控制",
      "get_current_user 从 token 解用户，require_role 限制角色",
      "不同角色权限隔离（如追溯接口仅 admin）",
      "JWT、权限矩阵")
    k("安全闸口", "Agent 安全",
      "二次确认（写操作挂起-恢复）、幻觉溯源（答案数值追溯工具返回）、降级人工复核（漏判不默认判轻）",
      "写操作安全不依赖 LLM 听话、防编造、危急缺陷不被放过",
      "ReAct、DB 只读角色")
    k("多轮记忆 + 实体锚点", "上下文管理",
      "设备栈（devices 列表）+ 焦点设备，注入系统提示，让 LLM 结合历史做指代消解",
      "「那第一台」「那它」等多轮指代不断片",
      "Redis、LLM 上下文")
    k("RAG 版本治理", "知识库管理",
      "front matter 存 version/status/superseded_by，检索过滤 superseded，版本仲裁自动废止旧版",
      "新标准更新后旧条文不被检索（避免给过时答案）",
      "ChromaDB where 过滤、markdown front matter")
    k("RealtimeSource 抽象", "数据接入",
      "抽象基类 + SimulatedSource 实现 + PMSSource 预留（字段映射表），业务只依赖接口",
      "模拟数据与真实 PMS 无缝切换，接真实数据不改业务代码",
      "适配器模式、ABC")
    k("MCP 协议", "工具标准化",
      "FastMCP 把平台工具暴露为标准 MCP 工具，挂载 /mcp 端点",
      "第三方 MCP 客户端（如 Claude Desktop）能直接调我们的工具",
      "mcp SDK、SSE")
    k("pytest", "测试框架",
      "@pytest.mark.parametrize 参数化对抗样本，50 个回归测试",
      "规则层/工具层改动回归保障",
      "压力测试方法论")
    k("并发 + SSE 桥接", "并发/流式",
      "ThreadPoolExecutor 并发请求，asyncio.Queue + threading 桥接同步 ReAct 与 SSE 流式",
      "多用户并发隔离 + 对话过程事件实时推送",
      "asyncio、FastAPI StreamingResponse")

    s.append(PageBreak())
    s.append(Paragraph("二、前端知识点", H2))

    k("HTML5 + CSS3", "标记语言 + 样式",
      "控制台布局（flex 侧边栏 + 主内容）、CSS 变量定义主题色、表格/卡片组件",
      "工程控制台界面（信息密集、克制）",
      "响应式设计", "前端")
    k("JavaScript（DOM + fetch）", "脚本语言",
      "getElementById 操作 DOM、addEventListener 事件、fetch 调接口、JSON.parse 解析",
      "前端交互逻辑：登录、切视图、发消息、渲染结果",
      "HTML DOM、异步（async/await）", "前端")
    k("SSE 流式读取", "流式通信",
      "fetch + res.body.getReader() + TextDecoder 逐块读，按 \\n\\n 分割解析 data 事件",
      "对话过程实时显示（意图/工具调用/最终答案）",
      "Server-Sent Events、ReadableStream", "前端")
    k("localStorage", "浏览器存储",
      "存 token、会话列表、各会话消息（JSON 序列化）",
      "会话历史本地持久化，刷新不丢",
      "JSON", "前端")
    k("CORS", "跨域",
      "后端 CORSMiddleware allow_origins=*，前端跨端口调 API",
      "前端页面（file:// 或不同端口）能调后端接口",
      "同源策略", "前端/后端")

    s.append(Paragraph("三、通用 / 工程知识点", H2))
    k("SRS 需求规格说明书", "文档规范",
      "按 GB/T 8567、IEEE 830 写需求，编号体系（FR/IF/DR/NFR/BR）+ 追踪矩阵 + 验收标准",
      "需求可追踪、可测试，设计开发有统一依据",
      "BR 业务规则、优先级定义", "通用")
    k("SDD 系统设计说明书", "文档规范",
      "分层架构图（mermaid）、模块设计、数据模型、接口、时序、安全、部署、ADR 决策记录",
      "设计可直接指导开发，决策有据可查",
      "mermaid、架构图", "通用")
    k("压力测试方法论", "测试策略",
      "对抗样本（否定句/口语/错别字/提示注入/反事实/边界）砸系统，暴露规则层缺陷",
      "从「100% 达标假象」逼出真缺陷（如漏判默认一般）",
      "pytest 参数化、红队测试", "通用")
    k("评估方法论", "评测",
      "Recall@k / MRR / 命中率测检索，准确率测分级，成本/延迟测 LLM",
      "量化系统质量，模型选型有数据支撑",
      "评测集构建、指标", "通用")
    k("可观测性", "运维",
      "logs（结构化日志）+ metrics（Prometheus /metrics）+ traces（trace 表 + 前端链路视图）",
      "系统状态可观察、问题可定位",
      "Prometheus、Grafana、OpenTelemetry", "通用/后端")
    k("Docker + docker-compose", "容器化",
      "docker-compose 起 postgres/chromadb/redis，镜像钉版本，registry-mirrors 加速",
      "一键起依赖，环境隔离，版本一致",
      "镜像、端口映射", "通用")
    k("环境管理 + 镜像源", "工程实践",
      "conda 环境、pip 清华源、HF hf-mirror 镜像 / HF_HUB_OFFLINE 离线、python -m 解决 PATH 不一致",
      "国内环境下载慢/解释器错位等实际问题",
      "pip/conda/HF", "通用")
    k("reportlab", "PDF 生成",
      "Platypus + UnicodeCIDFont('STSong-Light') 中文渲染，Table/Paragraph 排版",
      "生成中文项目文档 PDF",
      "中文字体、排版", "通用")
    return s


# ============================================================
# PDF 3：完整项目文档
# ============================================================
def project_pdf():
    s = title("电网智能运维助手 Agent 平台 · 项目文档", "需求 → 设计 → 实现 → 测试 → 加固 → 评估 → 交付 全记录")
    s.append(Paragraph("一、项目概述", H2))
    s.append(Paragraph("面向电网设备运维的智能助手，以「通用 Agent 引擎 + 统一数据模型 + 可插拔技能包」辅助运维人员完成知识问答、设备状态查询、告警分析、缺陷分级、故障诊断、工单生成六大业务。", P))
    s.append(Paragraph("二、架构", H2))
    s.append(Paragraph("自研轻量 ReAct（不用 LangChain）。分层：API(FastAPI) → Agent 引擎(意图路由/ReAct 主循环/工具调度/安全闸口/追溯/记忆) → 能力层(六大业务) → 技能包层 → 数据层(PostgreSQL + ChromaDB + Redis)。", P))
    s.append(Paragraph("三、三条安全原则", H2))
    s.append(Paragraph("C1 确定性优先：分级/诊断/数值走规则引擎，LLM 只编排；C2 写操作二次确认；C3 数据不足强制降级人工复核、不编造。", P))
    s.append(Paragraph("四、技术栈", H2))
    s.append(Table([
        ["层", "选型"],
        ["语言", "Python 3.10+（conda SAM2 环境）"],
        ["Web 框架", "FastAPI + uvicorn"],
        ["ORM/数据库", "SQLAlchemy 2.0 + PostgreSQL 16"],
        ["向量库", "ChromaDB 1.5.9 + bge-small-zh-v1.5 嵌入"],
        ["缓存/会话", "Redis 7"],
        ["LLM", "DeepSeek（deepseek-chat，OpenAI 兼容）"],
        ["前端", "纯 HTML/CSS/JS 控制台（外包中）"],
    ], style=TABLE_STYLE))
    s.append(Paragraph("五、功能清单", H2))
    s.append(Paragraph("六大业务：RAG 问答（带出处）、设备台账/量测/状态查询、告警分析、缺陷分级（规则引擎）、故障诊断（技能包）、工单生成（二次确认）。", P))
    s.append(Paragraph("工程能力：多用户 JWT 鉴权 + RBAC、多轮记忆 + 指代消解、RAG 版本治理、实时数据模拟 + PMS 适配预留、SSE 流式输出、MCP server、50 个回归测试、压力测试、评估报告。", P))
    s.append(Paragraph("六、目录结构", H2))
    s.append(Paragraph("app/（main、api、engine、skills、packs、data、core）+ rules/（YAML 规则）+ data/（模拟数据、docs 知识库）+ eval/（评测、压力测试、评估报告）+ scripts/（入库、模拟器、生成脚本）+ web/（前端）+ tests/（回归测试）。", P))
    s.append(Paragraph("七、API", H2))
    s.append(Paragraph("21 个 REST 接口，统一 {code,message,data}，JWT Bearer 认证，详见《API接口文档.md》和 Swagger /docs。", P))
    s.append(Paragraph("八、部署", H2))
    s.append(Paragraph("docker compose 起 postgres/chromadb/redis；python -m app.data.database 建表建角色；python data/generate_mock.py 灌数据；python scripts/ingest_kb.py 入库；python scripts/simulate_live.py 实时模拟；python -m uvicorn app.main:app 起服务。", P))
    s.append(Paragraph("九、验收状态", H2))
    s.append(Table([
        ["指标", "结果"],
        ["回归测试", "50 passed"],
        ["缺陷分级准确率", "24/24 = 100%"],
        ["意图识别（规则层）", "18/19 = 94.7%"],
        ["嵌入检索 Recall@5", "78.79%（四模型一致）"],
        ["LLM 成本", "≈0.0008 元/问，稳态 3s/问"],
        ["提示注入", "全部守住"],
    ], style=TABLE_STYLE))
    s.append(Paragraph("十、关键经验教训", H2))
    s.append(Paragraph("1. 压力测试才能暴露真问题（干净评估集是假象）；2. 安全靠架构兜底不靠模型听话；3. 关键词规则永远补不全，但「降级人工复核」能把补不全变成安全的。", P))
    return s


def main():
    build_pdf("差距与上线待办.pdf", gap_pdf())
    build_pdf("技术知识点全解.pdf", knowledge_pdf())
    build_pdf("项目文档.pdf", project_pdf())
    print("三份 PDF 生成完成")


if __name__ == "__main__":
    main()
