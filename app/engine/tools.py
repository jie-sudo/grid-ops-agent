"""工具定义与注册表（SDD 4.1.3）。

每个业务能力封装为一个 Tool（name / 描述 / 参数 schema / 处理器 / 只读标记），
M4 的工具调度器据此校验并执行。
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable


@dataclass
class Tool:
    name: str
    description: str
    params_schema: dict[str, Any]  # JSON Schema 风格参数定义
    handler: Callable[..., Any]
    read_only: bool = True


_REGISTRY: dict[str, Tool] = {}


def register(tool: Tool) -> None:
    _REGISTRY[tool.name] = tool


def get_tool(name: str) -> Tool | None:
    return _REGISTRY.get(name)


def list_tools() -> list[Tool]:
    return list(_REGISTRY.values())
