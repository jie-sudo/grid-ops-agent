"""生成《项目交接文档》PDF（自动换行版）。用法：python scripts/gen_handover_pdf.py"""
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

H1 = ParagraphStyle("h1", fontName="STSong-Light", fontSize=20, leading=28, alignment=1, spaceAfter=4, wordWrap="CJK")
SUB = ParagraphStyle("sub", fontName="STSong-Light", fontSize=10, leading=14, alignment=1, textColor=colors.grey, wordWrap="CJK")
H2 = ParagraphStyle("h2", fontName="STSong-Light", fontSize=14, leading=20, spaceBefore=14, spaceAfter=6, textColor=colors.HexColor("#2563eb"), wordWrap="CJK")
H3 = ParagraphStyle("h3", fontName="STSong-Light", fontSize=12, leading=18, spaceBefore=10, spaceAfter=4, wordWrap="CJK")
P = ParagraphStyle("p", fontName="STSong-Light", fontSize=10, leading=16, wordWrap="CJK")
B = ParagraphStyle("b", fontName="STSong-Light", fontSize=10, leading=16, leftIndent=12, wordWrap="CJK")
CODE = ParagraphStyle("code", fontName="Courier", fontSize=9, leading=13, leftIndent=12, textColor=colors.HexColor("#0f172a"), wordWrap="LTR")
CELL = ParagraphStyle("cell", fontName="STSong-Light", fontSize=9, leading=13, wordWrap="CJK")
CELL_HDR = ParagraphStyle("cellhdr", fontName="STSong-Light", fontSize=9, leading=13, textColor=colors.white, wordWrap="CJK")

TABLE_STYLE = TableStyle([
    ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#2563eb")),
    ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#d9e0e7")),
    ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
    ("TOPPADDING", (0, 0), (-1, -1), 4),
    ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
])


def mk_table(header, rows, widths):
    data = [[Paragraph(h, CELL_HDR) for h in header]] + [
        [Paragraph(str(c), CELL) for c in row] for row in rows
    ]
    t = Table(data, colWidths=widths)
    t.setStyle(TABLE_STYLE)
    return t


def main():
    doc = SimpleDocTemplate(str(ROOT / "项目交接文档.pdf"), pagesize=A4, topMargin=40, bottomMargin=40, leftMargin=48, rightMargin=48)
    s = []
    s.append(Paragraph("电网智能运维助手 Agent 平台 · 项目交接文档", H1))
    s.append(Paragraph("供前端工程师 / 后端工程师 / 运维 / 后续开发者快速上手", SUB))
    s.append(Spacer(1, 16))

    s.append(Paragraph("一、项目概览", H2))
    s.append(Paragraph("面向电网设备运维的智能助手，以「通用 Agent 引擎 + 统一数据模型 + 可插拔技能包」辅助完成知识问答、设备查询、告警分析、缺陷分级、故障诊断、工单生成。", P))
    s.append(mk_table(
        ["技术栈", "选型"],
        [
            ["后端语言", "Python 3.10+（conda 环境 SAM2）"],
            ["Web 框架", "FastAPI + uvicorn"],
            ["数据库", "PostgreSQL 16 + SQLAlchemy 2.0"],
            ["向量库", "ChromaDB 1.5.9 + bge-small-zh-v1.5 嵌入"],
            ["缓存/会话", "Redis 7"],
            ["LLM", "DeepSeek（deepseek-chat，OpenAI 兼容）"],
            ["前端", "纯 HTML/CSS/JS 控制台（web/index.html，外包中）"],
        ],
        [140, 359],
    ))
    s.append(Paragraph("配套文档：SRS 需求说明书、SDD 系统设计、API接口文档.md、开发经验总结.md、评估报告.md、技术知识点全解.pdf。", P))

    s.append(Paragraph("二、后端交接", H2))
    s.append(Paragraph("2.1 架构分层", H3))
    s.append(Paragraph("API(FastAPI) → Agent 引擎(意图路由/ReAct 主循环/工具调度/安全闸口/追溯/记忆) → 能力层(六大业务) → 技能包层 → 数据层(PostgreSQL+ChromaDB+Redis)。", P))
    s.append(Paragraph("2.2 目录结构（app/ 各模块职责）", H3))
    s.append(mk_table(
        ["目录", "职责"],
        [
            ["app/main.py", "入口：路由装配、CORS、MCP 挂载"],
            ["app/api/", "REST 路由：auth/chat/devices/alarms/defects/diagnoses/workorders/knowledge/tools/traces/sessions/health"],
            ["app/engine/", "Agent 引擎：intent_router(意图)、react_loop(ReAct 主循环，核心)、tool_dispatcher(工具调度)、guards(安全闸口)、tracer(追溯)、memory(记忆)、llm(LLM 客户端)、rule_engine(规则引擎)"],
            ["app/skills/", "业务能力：rag/query/alarm/defect/diagnosis/workorder"],
            ["app/packs/", "技能包：base + switchgear/transformer/cable"],
            ["app/data/", "数据层：models(ORM)/repository(仓储)/database(连接)/vectorstore(向量)/kb(语料)/ingest(入库)/realtime(实时数据源)/adapter(接入)"],
            ["app/core/", "基础设施：auth(JWT/RBAC)/errors(错误码)/logging"],
            ["rules/", "YAML 规则：level_mapping(等级映射)/defect_level(分级关键词)/thresholds(技能包阈值)"],
            ["data/", "模拟数据脚本 + docs(34 篇知识库语料)"],
            ["eval/", "评测脚本、压力测试、评估报告"],
            ["scripts/", "入库、实时模拟器、PDF 生成、用户初始化"],
            ["tests/", "50 个回归测试"],
        ],
        [90, 409],
    ))
    s.append(Paragraph("2.3 关键模块（改代码前先读这些）", H3))
    s.append(Paragraph("<b>react_loop.py</b>：ReAct 主循环，最复杂。含步数上限、死循环检测、二次确认挂起、反问澄清、幻觉溯源、实体锚点、SSE on_event 回调。", B))
    s.append(Paragraph("<b>rule_engine.py</b>：规则引擎。缺陷分级（关键词+否定词+漏判降级人工复核）、等级映射、时限。", B))
    s.append(Paragraph("<b>guards.py</b>：安全闸口。二次确认判定、降级识别、幻觉溯源。", B))
    s.append(Paragraph("<b>realtime.py</b>：实时数据源抽象。SimulatedSource + PMSSource 预留（接真实数据的入口）。", B))
    s.append(Paragraph("2.4 数据模型（表清单）", H3))
    s.append(Paragraph("业务表：device/measure_point/measure_value(时序分表)/defect/alarm/work_order/knowledge_doc。支撑表：app_user/session/trace/message/session_summary。", P))
    s.append(Paragraph("2.5 API 接口（21 个，详见 API接口文档.md）", H3))
    s.append(Paragraph("认证：auth/login。对话：chat(同步)、chat/stream(SSE)。会话/设备/告警/缺陷/诊断/工单/知识库/工具/追溯/健康各若干。统一 {code,message,data}，JWT Bearer。", P))

    s.append(PageBreak())
    s.append(Paragraph("三、前端交接", H2))
    s.append(Paragraph("3.1 现状", H3))
    s.append(Paragraph("web/index.html 是纯 HTML 控制台（无构建），五视图：对话工作台/运行链路/工具注册/知识库/系统健康。前端正式版外包中，后端接口已备好。", P))
    s.append(Paragraph("3.2 接口对接要点", H3))
    s.append(mk_table(
        ["要点", "说明"],
        [
            ["认证", "POST /auth/login 拿 token，之后请求头带 Authorization: Bearer <token>"],
            ["对话", "用 POST /chat/stream（SSE），逐事件渲染（intent/tool_call/clarify/confirm_required/final_answer）"],
            ["二次确认", "收到 confirm_required 时弹确认框，用户回复「确认/取消」再走 /chat/stream"],
            ["设备选择", "GET /devices?keyword= 搜索，选中后把设备编号拼进消息（如「设备 DEV000001：温度多少」）"],
            ["实时监控", "轮询 GET /devices/{id}/overview（台账+四态+量测+告警）"],
            ["运行链路", "GET /traces/{session_id}（需 admin）"],
        ],
        [90, 409],
    ))
    s.append(Paragraph("3.3 参考实现", H3))
    s.append(Paragraph("web/index.html 已有全部交互逻辑（登录/流式渲染/设备选择器/二次确认），前端工程师可参照它用 React/Vue 重实现。参考 PRD：DevInfra Agent Console（控制台风格）。", P))

    s.append(Paragraph("四、怎么使用", H2))
    s.append(Paragraph("4.1 环境准备", H3))
    s.append(Paragraph("Windows + PowerShell；conda 环境 SAM2（Python 3.10）；pip 清华源；HF 镜像 hf-mirror（或 HF_HUB_OFFLINE=1 离线）。", P))
    s.append(Paragraph("4.2 启动步骤", H3))
    for line in [
        "1. docker compose up -d postgres redis chromadb（起依赖）",
        "2. python -m app.data.database（建表+建角色）",
        "3. python scripts/init_users.py（初始化账号）",
        "4. python data/generate_mock.py --scale demo（灌模拟数据）",
        "5. python scripts/ingest_kb.py（知识库入库）",
        "6. python scripts/simulate_live.py（实时数据模拟，可选，保持运行）",
        "7. python -m uvicorn app.main:app --reload（起服务）",
    ]:
        s.append(Paragraph(line, CODE))
    s.append(Paragraph("注意：必须用 python -m uvicorn / python -m pytest，裸命令会解析到错误的 Python 版本。", P))
    s.append(Paragraph("4.3 登录账号", H3))
    s.append(Paragraph("admin/admin123（管理员）、operator/operator123（运维）、monitor/monitor123、manager/manager123。", P))
    s.append(Paragraph("4.4 常用操作", H3))
    s.append(Paragraph("对话问答、设备查询（搜索选择设备后自然提问）、工单生成（二次确认落库）、知识库检索、查看运行链路、系统健康。", P))

    s.append(Paragraph("五、怎么接（接入指南）", H2))
    s.append(Paragraph("5.1 接 LLM（换模型/换 key）", H3))
    s.append(Paragraph("改 .env 的 LLM_BASE_URL / LLM_API_KEY / LLM_MODEL。任何 OpenAI 兼容模型（Qwen、GPT、GLM）都行，改配置即可。", P))
    s.append(Paragraph("5.2 接真实数据（PMS/监测系统）", H3))
    s.append(Paragraph("1. 在 app/data/realtime.py 实现 PMSSource.get_latest()（骨架 + 字段映射表已写好）。", CODE))
    s.append(Paragraph("2. 改 get_source() 返回 PMSSource(base_url=..., api_key=...)。", CODE))
    s.append(Paragraph("3. 业务代码（overview/状态评价）零改动，因为只依赖 RealtimeSource 接口。", P))
    s.append(Paragraph("5.3 接新技能包（新设备类型）", H3))
    s.append(Paragraph("1. app/packs/ 新建目录 + 类（继承 BaseSkillPack，设 key/device_type）。", CODE))
    s.append(Paragraph("2. rules/thresholds/ 加对应阈值 YAML（checks 列表）。", CODE))
    s.append(Paragraph("3. app/packs/__init__.py 注册新类。不改引擎。", P))
    s.append(Paragraph("5.4 接新语料（加文档 + 版本管理）", H3))
    s.append(Paragraph("1. data/docs/ 放新 .md，带 front matter（version/status/effective_date/superseded_by）。", CODE))
    s.append(Paragraph("2. 调 POST /knowledge/ingest（admin）或 python scripts/ingest_kb.py。", CODE))
    s.append(Paragraph("3. 版本管理：同 version 多个 effective_date 自动废止旧的；检索只返回 active。", P))
    s.append(Paragraph("5.5 前端接后端", H3))
    s.append(Paragraph("按「三、前端交接」的对接要点 + API接口文档.md 开发，先跑通登录 + 一次流式对话即可独立开发。", P))
    s.append(Paragraph("5.6 接 MCP 客户端", H3))
    s.append(Paragraph("平台已暴露 MCP server（/mcp 端点，6 个工具）。MCP 客户端（如 Claude Desktop）配置该端点即可调 query_device/grade_defect/diagnose 等工具。", P))

    s.append(Paragraph("六、关键坑与注意事项", H2))
    s.append(mk_table(
        ["坑", "表现", "处理"],
        [
            ["python -m 问题", "裸 uvicorn/pytest 解析到 Python 3.13 报错", "统一用 python -m uvicorn / python -m pytest"],
            ["HF 下载慢", "模型直连 huggingface 超时", "HF_ENDPOINT=hf-mirror.com 或 HF_HUB_OFFLINE=1"],
            ["chromadb 版本", "客户端/服务端不匹配 404", "两者都钉 1.5.9，端口 8001"],
            ["漏判默认一般", "危急缺陷被误判", "已改为漏判降级人工复核，勿改回"],
            ["写操作安全", "靠二次确认 + DB 只读角色", "勿绕过闸口，勿给查询账号写权限"],
            ["嵌入模型", "bge-small 已选定", "评测四模型精度无差，small 最快，勿无脑换大的"],
        ],
        [110, 170, 219],
    ))

    doc.build(s)
    print(f"已生成：{ROOT / '项目交接文档.pdf'}")


if __name__ == "__main__":
    main()
