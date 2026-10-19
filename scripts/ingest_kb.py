"""知识库入库脚本（幂等 + 版本仲裁）。用法：python scripts/ingest_kb.py"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.data.ingest import ingest_knowledge


def main() -> None:
    r = ingest_knowledge()
    print(f"入库完成：{r['docs']} 篇文档，{r['chunks']} 个片段（其中 {r['active_chunks']} 个 active 参与检索）")
    if r["superseded_docs"]:
        print(f"自动废止（版本仲裁）：{', '.join(r['superseded_docs'])}")


if __name__ == "__main__":
    main()
