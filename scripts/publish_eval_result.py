"""把离线评测结果固化到 eval_run 表，供评估看板（GET /evals/summary）展示。

评测脚本（eval_retrieval / eval_defect_grading / eval_rerank 等）是重离线计算，
跑完把关键指标用本脚本落库即可，前端看板读最新一条。

用法：
    python scripts/publish_eval_result.py --suite retrieval --json '{"R@5":0.923,"R@10":0.95}' --sample 300
    python scripts/publish_eval_result.py --suite grading --json '{"hit":0.71,"degrade":0.29,"wrong":0.0}' --sample 500 --note "bigram 定级，0 误判"

指标约定（前端看板按 suite 渲染）：
- retrieval: {"R@5": float, "R@10": float, "R@5_rerank": float, ...}
- grading:   {"hit": float, "degrade": float, "wrong": float, ...}
- stress:    {"p50_ms": float, "p95_ms": float, "success_rate": float, ...}
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.data import repository


def main() -> None:
    ap = argparse.ArgumentParser(description="固化评测结果到 eval_run 表")
    ap.add_argument("--suite", required=True, help="评测套件：retrieval/grading/stress")
    ap.add_argument("--json", required=True, help="指标 JSON 字符串，如 '{\"R@5\":0.92}'")
    ap.add_argument("--sample", type=int, default=0, help="样本量")
    ap.add_argument("--note", default=None, help="备注（版本/模型/结论）")
    ap.add_argument("--run-id", default=None, help="自定义 run_id（默认自动生成）")
    args = ap.parse_args()

    try:
        metrics = json.loads(args.json)
    except json.JSONDecodeError as e:
        print(f"指标 JSON 解析失败：{e}", file=sys.stderr)
        sys.exit(1)

    result = repository.save_eval_run(
        suite=args.suite,
        metrics=metrics,
        sample_n=args.sample,
        note=args.note,
        run_id=args.run_id,
    )
    print(f"已固化：run_id={result['run_id']} suite={result['suite']} metrics={metrics}")


if __name__ == "__main__":
    main()
