"""LLM 成本 + 耗时测算：跑若干代表性问题，统计 token 用量、延迟、估算成本。

用法（需 postgres + redis 运行）：python eval/llm_cost.py
"""
from __future__ import annotations

import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

# DeepSeek 定价（元/百万 token）——务必按实际账单核对，价格会变
PRICE_INPUT = 0.27   # 输入（缓存未命中）
PRICE_OUTPUT = 1.1   # 输出

# 代表性问题（覆盖问答/查询/工单三类）
QUESTIONS = [
    "变压器的缺陷分级有哪几级",
    "查询设备 DEV000001 的台账",
    "帮我出个工单：变压器油温严重超标",
]


def main() -> None:
    from app.engine.react_loop import AgentLoop
    from app.engine.tracer import Tracer

    loop = AgentLoop()
    tracer = Tracer()
    latencies = []
    for q in QUESTIONS:
        sid = tracer.start_session()
        t0 = time.time()
        result = loop.run(sid, q)
        lat = time.time() - t0
        latencies.append(lat)
        print(f"[{lat:5.1f}s] {q}  →  {result.get('type')}")

    usage = loop.llm.get_usage()
    cost = (
        usage["prompt_tokens"] / 1e6 * PRICE_INPUT
        + usage["completion_tokens"] / 1e6 * PRICE_OUTPUT
    )
    print("\n=== LLM 用量与成本 ===")
    print(f"调用次数：{usage['call_count']}")
    print(f"输入 token：{usage['prompt_tokens']}")
    print(f"输出 token：{usage['completion_tokens']}")
    print(f"平均延迟：{usage['avg_latency_ms']} ms，最大：{usage['max_latency_ms']} ms")
    print(f"端到端平均每问：{sum(latencies) / len(latencies):.1f}s")
    print(f"估算成本：¥{cost:.4f}（{len(QUESTIONS)} 问，输入 {PRICE_INPUT} 元/M、输出 {PRICE_OUTPUT} 元/M）")


if __name__ == "__main__":
    main()
