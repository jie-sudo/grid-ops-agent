"""MCP 服务器：把平台能力暴露为标准 MCP 工具（供 Claude Desktop 等 MCP 客户端调用）。

依赖：pip install "mcp<2"。端点挂载在 /mcp（SSE）。
"""
from __future__ import annotations

try:
    from mcp.server.fastmcp import FastMCP  # mcp 1.x

    _Server = FastMCP
except ImportError:
    from mcp.server.mcpserver import MCPServer  # mcp 2.x

    _Server = MCPServer

from app.data import repository
from app.skills import defect, diagnosis, query, rag

mcp = _Server("grid-ops-agent")


@mcp.tool()
def query_device(device_id: str) -> dict:
    """按设备编号查询台账。"""
    return query.query_device(device_id)


@mcp.tool()
def list_devices(keyword: str = "", limit: int = 50) -> dict:
    """设备列表 + 模糊搜索（名称/站所/类型）。"""
    devices = repository.list_devices(keyword or None, limit)
    return {"devices": devices, "count": len(devices)}


@mcp.tool()
def grade_defect(description: str) -> dict:
    """缺陷等级判定（一般/严重/危急，无法确定则降级人工复核）。"""
    return defect.grade_defect(description)


@mcp.tool()
def diagnose(device_type: str, measurements: dict) -> dict:
    """设备故障诊断（确定性规则）。"""
    return diagnosis.diagnose(device_type, measurements)


@mcp.tool()
def retrieve_knowledge(question: str, top_k: int = 5) -> dict:
    """检索知识库，返回带出处的文档片段。"""
    return rag.retrieve_knowledge(question, top_k)


@mcp.tool()
def deadline_for(level: str) -> dict:
    """缺陷等级 → 消缺时限。"""
    return defect.deadline_for(level)
