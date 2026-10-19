from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import alarms, auth, chat, defects, devices, diagnoses, evals, health, knowledge, messages, metrics, review_cases, sessions, tools, traces, workorders
from app.config import get_settings
from app.core.logging import setup_logging

setup_logging()

app = FastAPI(title=get_settings().app_name, version="0.1.0")

# CORS：允许前端 Demo（web/index.html）跨域调用
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health.router, prefix="/api/v1", tags=["health"])
app.include_router(auth.router, prefix="/api/v1", tags=["auth"])
app.include_router(chat.router, prefix="/api/v1", tags=["chat"])
app.include_router(devices.router, prefix="/api/v1", tags=["devices"])
app.include_router(alarms.router, prefix="/api/v1", tags=["alarms"])
app.include_router(defects.router, prefix="/api/v1", tags=["defects"])
app.include_router(diagnoses.router, prefix="/api/v1", tags=["diagnoses"])
app.include_router(workorders.router, prefix="/api/v1", tags=["workorders"])
app.include_router(sessions.router, prefix="/api/v1", tags=["sessions"])
app.include_router(knowledge.router, prefix="/api/v1", tags=["knowledge"])
app.include_router(tools.router, prefix="/api/v1", tags=["tools"])
app.include_router(traces.router, prefix="/api/v1", tags=["traces"])
app.include_router(messages.router, prefix="/api/v1", tags=["messages"])
app.include_router(review_cases.router, prefix="/api/v1", tags=["review-cases"])
app.include_router(metrics.router, prefix="/api/v1", tags=["metrics"])
app.include_router(evals.router, prefix="/api/v1", tags=["evals"])

# MCP 服务器（SSE 端点 /mcp），供标准 MCP 客户端接入
try:
    from app.mcp_server import mcp

    app.mount("/mcp", mcp.sse_app())
except Exception as e:  # mcp 未安装或版本不兼容时不阻塞主服务
    import logging

    logging.getLogger(__name__).warning(f"MCP 挂载失败（可忽略）：{e}")


@app.get("/")
async def root() -> dict:
    return {"service": get_settings().app_name, "docs": "/docs", "health": "/api/v1/health"}
