"""LLM 连通性自检：读取 .env 配置，用 LLMClient 调一次 DeepSeek。"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.engine.llm import LLMClient, LLMError


def main() -> None:
    c = LLMClient()
    print(f"base_url: {c.base_url}")
    print(f"model:    {c.model}")
    try:
        reply = c.chat([{"role": "user", "content": "回复OK两个字"}])
        print(f"回复:     {reply}")
        print("LLM 连通性 OK")
    except LLMError as e:
        print(f"调用失败: {e}")


if __name__ == "__main__":
    main()
