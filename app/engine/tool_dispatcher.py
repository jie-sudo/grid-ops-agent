"""工具调度器：schema 校验 + 执行 + 结果序列化（SDD 4.1.3，FR-003）。"""
from __future__ import annotations

import json
import time

from app.engine.tools import get_tool, list_tools
from app.tools import register_all_tools


def _coerce(spec: str, value):
    """把参数按 "type=default" 规格转换类型。"""
    type_str, _, default = spec.partition("=")
    if value is None:
        if default == "" or default == "None":
            return None
        value = default
    if value is None:
        return None
    try:
        if type_str == "int":
            return int(value)
        if type_str == "float":
            return float(value)
        if type_str == "str":
            return str(value)
        if type_str == "dict":
            return value if isinstance(value, dict) else json.loads(value)
        if type_str == "bool":
            return bool(value)
    except (ValueError, json.JSONDecodeError):
        raise ValueError(f"参数类型应为 {type_str}，实际为 {value!r}")
    return value


class ToolDispatcher:
    def __init__(self) -> None:
        register_all_tools()

    def list_schemas(self) -> list[dict]:
        return [
            {"name": t.name, "description": t.description, "params": t.params_schema}
            for t in list_tools()
        ]

    def validate(self, tool_name: str, params: dict | None) -> tuple[dict | None, str | None]:
        tool = get_tool(tool_name)
        if tool is None:
            return None, f"工具不存在: {tool_name}"
        params = params or {}
        coerced: dict = {}
        for key, spec in tool.params_schema.items():
            if key in params:
                try:
                    coerced[key] = _coerce(spec, params[key])
                except ValueError as e:
                    return None, f"参数错误: {e}"
            elif "=" in spec:
                coerced[key] = _coerce(spec, None)
            else:
                return None, f"缺少必填参数: {key}"
        return coerced, None

    def execute(self, tool_name: str, params: dict | None = None) -> dict:
        """执行工具，返回结构化结果；任何异常都不外泄原始堆栈。"""
        tool = get_tool(tool_name)
        if tool is None:
            return {"error": f"工具不存在: {tool_name}"}
        coerced, err = self.validate(tool_name, params)
        if err:
            return {"error": err}
        try:
            result = tool.handler(**coerced)
            return result if isinstance(result, dict) else {"result": result}
        except Exception:
            return {"error": f"工具执行失败: {tool_name}"}
