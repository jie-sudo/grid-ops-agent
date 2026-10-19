"""LLM 客户端：OpenAI 兼容协议（httpx 手写，不依赖框架，可替换模型，见 IF-002）。"""
from __future__ import annotations

import json
import time

import httpx

from app.config import get_settings


class LLMError(Exception):
    """LLM 调用异常（统一包装，不向外泄露原始堆栈）。"""


class LLMClient:
    def __init__(
        self,
        base_url: str | None = None,
        api_key: str | None = None,
        model: str | None = None,
    ) -> None:
        s = get_settings()
        self.base_url = (base_url or s.llm_base_url).rstrip("/")
        self.api_key = api_key or s.llm_api_key
        self.model = model or s.llm_model
        self.timeout = s.llm_timeout
        # token 用量统计（成本测算）
        self.usage = {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}
        self.last_usage: dict | None = None  # 最近一次调用的 usage（供预算账本结算）
        self.call_count = 0
        self.latencies: list[int] = []  # 每次调用耗时(ms)

    def chat(self, messages: list[dict], temperature: float = 0.0) -> str:
        t0 = time.time()
        self.last_usage = None  # 本次调用成功才赋值；失败则保留 None（预算按"未知"结算）
        url = f"{self.base_url}/chat/completions"
        headers = {"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"}
        payload = {"model": self.model, "messages": messages, "temperature": temperature}
        try:
            with httpx.Client(timeout=self.timeout) as client:
                resp = client.post(url, json=payload, headers=headers)
                resp.raise_for_status()
                data = resp.json()
        except httpx.HTTPStatusError as e:
            raise LLMError(f"LLM 调用失败 HTTP {e.response.status_code}") from e
        except httpx.HTTPError as e:
            raise LLMError(f"LLM 调用超时/网络错误") from e
        usage = data.get("usage", {})
        self.last_usage = usage
        self.usage["prompt_tokens"] += usage.get("prompt_tokens", 0)
        self.usage["completion_tokens"] += usage.get("completion_tokens", 0)
        self.usage["total_tokens"] += usage.get("total_tokens", 0)
        self.call_count += 1
        self.latencies.append(int((time.time() - t0) * 1000))
        return data["choices"][0]["message"]["content"]

    def chat_json(self, messages: list[dict]) -> dict:
        """调用并要求返回 JSON（用于 ReAct 工具调用协议）。"""
        raw = self.chat(messages).strip()
        if raw.startswith("```"):
            raw = raw.strip("`")
            if raw.lower().startswith("json"):
                raw = raw[4:]
            raw = raw.strip()
        try:
            return json.loads(raw)
        except json.JSONDecodeError as e:
            raise LLMError(f"LLM 输出非合法 JSON: {raw[:200]}") from e

    def get_usage(self) -> dict:
        """累计 token 用量 + 调用次数 + 耗时（供成本测算）。"""
        avg = sum(self.latencies) / len(self.latencies) if self.latencies else 0
        return {
            **self.usage,
            "call_count": self.call_count,
            "avg_latency_ms": int(avg),
            "max_latency_ms": max(self.latencies) if self.latencies else 0,
        }
