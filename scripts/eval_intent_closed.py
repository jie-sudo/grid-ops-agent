"""意图识别「闭卷口语」评测：规则层覆盖/精确 + 完整链路准确率 + 混淆矩阵。

背景：意图是软先验、不锁工具，误判代价低于缺陷分级，但规则层关键词太贪（如「缺陷」
抢在「问答」前命中），闭卷口语（不带触发关键词）下规则层会大量漏判、依赖 LLM 兜底。
本脚本量化三件事：
- 规则层覆盖率：多少问句规则层能命中
- 规则层精确率：命中里判对多少（未命中则交给 LLM 兜底）
- 完整链路（规则 + LLM 兜底）准确率 + 混淆矩阵 + 误判样例

用法：
    python scripts/eval_intent_closed.py --rules-only        # 只测规则层（不调 LLM，零成本）
    python scripts/eval_intent_closed.py                     # 完整链路（规则 + LLM 兜底）
    python scripts/eval_intent_closed.py --sample 20         # 采样快跑
"""
from __future__ import annotations

import argparse
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.engine.intent_router import INTENTS, IntentRouter

EVAL = Path(__file__).resolve().parents[1] / "eval" / "qa_closed_intent.py"


# 旧七类 → 新五类 标签迁移（告警/缺陷/诊断合并为异常处置）；新生成的五类标签原样保留。
LABEL_MAP = {"告警分析": "异常处置", "缺陷分级": "异常处置", "故障诊断": "异常处置"}


def load() -> list[dict]:
    ns: dict = {}
    exec(EVAL.read_text(encoding="utf-8"), ns)
    rows = []
    for r in ns["CLOSED_INTENT"]:
        r = dict(r)
        r["intent"] = LABEL_MAP.get(r["intent"], r["intent"])
        rows.append(r)
    return rows


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--sample", type=int, default=0, help="采样条数（0=全量）")
    ap.add_argument("--rules-only", action="store_true", help="只测规则层，不调 LLM（离线零成本）")
    args = ap.parse_args()

    data = load()
    if args.sample and args.sample < len(data):
        data = data[: args.sample]
    n = len(data)

    router = IntentRouter()
    print(f"闭卷口语意图评测集 {n} 条（{'规则层' if args.rules_only else '规则 + LLM 兜底'}）\n")

    # 统计
    rule_fired = 0
    rule_correct = 0
    full_correct = 0
    conf = defaultdict(lambda: defaultdict(int))  # conf[gold][pred]
    rule_wrong_cases: list[tuple[str, str, str]] = []  # (text, gold, rule_pred)
    full_wrong_cases: list[tuple[str, str, str]] = []  # (text, gold, full_pred)

    for i, r in enumerate(data, 1):
        text, gold = r["text"], r["intent"]

        rp = router.route_rules(text)
        if rp is not None:
            rule_fired += 1
            r_pred = rp[0]
            if r_pred == gold:
                rule_correct += 1
            else:
                rule_wrong_cases.append((text, gold, r_pred))
        else:
            r_pred = None  # 规则层未命中 → 生产走 LLM 兜底

        if args.rules_only:
            full_pred = r_pred or "其他"  # 离线口径：规则层未命中按 LLM 兜底最坏情况记为「其他」
        else:
            full_pred = router.route(text)[0]
        if full_pred == gold:
            full_correct += 1
        else:
            full_wrong_cases.append((text, gold, full_pred))
        conf[gold][full_pred] += 1

        if i % 20 == 0:
            print(f"  进度 {i}/{n}", flush=True)

    # 规则层口径
    print("=" * 60)
    print("【规则层】")
    print(f"  覆盖率：{rule_fired}/{n} = {rule_fired/n:.1%}（其余交给 LLM 兜底）")
    prec = rule_correct / rule_fired if rule_fired else 0.0
    print(f"  精确率：命中 {rule_fired} 条里判对 {rule_correct} = {prec:.1%}")
    print(f"  整体准确：{rule_correct}/{n} = {rule_correct/n:.1%}（未命中记 0）")
    if rule_wrong_cases:
        print("  规则层误判样例：")
        for c in rule_wrong_cases[:10]:
            print(f"    [{c[1]}→{c[2]}] {c[0]}")

    # 完整链路口径
    print("=" * 60)
    print(f"【完整链路{'（规则 + LLM 兜底）' if not args.rules_only else '（离线近似）'}】")
    print(f"  准确率：{full_correct}/{n} = {full_correct/n:.1%}")
    if not args.rules_only:
        print(f"  LLM 调用失败：{router.llm_failures} 次（若 >0，本轮结果不可信——失败被静默算成「其他」）")
    if full_wrong_cases:
        print("  误判样例：")
        for c in full_wrong_cases[:15]:
            print(f"    [{c[1]}→{c[2]}] {c[0]}")

    # 混淆矩阵
    print("=" * 60)
    print("【混淆矩阵】行=真值，列=预测")
    header = "        " + "".join(f"{it[:4]:>6}" for it in INTENTS)
    print(header)
    for gold in INTENTS:
        row = f"{gold[:4]:>6}"
        for pred in INTENTS:
            row += f"{conf[gold][pred]:>6}"
        print(row)

    # 每类召回率（完整链路）
    print("=" * 60)
    print("【各类别召回率（完整链路）】")
    for gold in INTENTS:
        total = sum(conf[gold].values())
        if total:
            rec = conf[gold][gold] / total
            print(f"  {gold}：{conf[gold][gold]}/{total} = {rec:.1%}")


if __name__ == "__main__":
    main()
