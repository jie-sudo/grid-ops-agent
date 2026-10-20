"""生成「闭卷口语意图评测集」：让 LLM 直接批量生成多样口语问句（强制禁用触发关键词 + 强制不重复 + 去重）。

为什么需要它：意图规则层是关键词匹配，用「带关键词」的规范问句评测会系统性高估（开卷）。
本脚本让 LLM 按每个意图的「一线口语」定义，直接生成大量不同说法的口语问句，并强制：
- 禁用触发关键词（否则又变开卷）；
- 每条说法不同（否则几百条里一半是重复，样本量注水）；
- 生成后做字面/归一化去重。

意图为自动标注，**需 100% 人工审核**（同时生成审核清单）。

用法：
    python scripts/gen_closed_intent_set.py --target-per-intent 20        # 每类 20，共 ~100
    python scripts/gen_closed_intent_set.py --target-per-intent 140       # 每类 140，共 ~700（SRS 验收量）
    python scripts/gen_closed_intent_set.py --intent 工单生成 --target-per-intent 50
    python scripts/gen_closed_intent_set.py --fresh                        # 清空旧评测集重新生成
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.engine.intent_router import INTENTS
from app.engine.llm import LLMClient, LLMError

OUT = Path(__file__).resolve().parents[1] / "eval" / "qa_closed_intent.py"
REVIEW = Path(__file__).resolve().parents[1] / "eval" / "qa_closed_intent_review.md"

# 每个意图的「一线口语」定义（生成依据），供 LLM 理解该生成什么样的句子。
INTENT_DEFS: dict[str, str] = {
    "问答": "问通用的规程/标准/依据/周期做法，不指向某台具体设备此刻的异常。如：断路器多久检修一次、渗油的处理规程是啥。",
    "状态查询": "问某台具体设备此刻的读数或状态。如：1号主变多少度、母线多少伏、断路器合着还是断着、这台设备啥情况。",
    "异常处置": "设备或事件出了异常，要分析原因、定级或处理。如：主变漏油了咋回事、这毛病算哪一级、开关柜滋滋响啥原因。",
    "工单生成": "明确要安排人去处理。如：开个单让人去修、派个活处理一下、帮我记一下安排人、这缺陷派人去弄。",
    "其他": "与电网运维无关、或不在本助手职责范围内的请求。要生成「领域擦边但该拒」的硬样本，涵盖：① 家用/民用设备问题（空调/冰箱/热水器坏了）；② 非运维事务（写总结/做报表/客服咨询/收费问题）；③ 对电力术语的纯科普提问（'变压器是干嘛用的'，不是要处理某台设备）；④ 明显无关的闲聊（天气/吃饭/写诗）。不要只生成天气吃饭这种一眼垃圾。",
}

# 每个意图的「风格参考示例」：只用于告诉 LLM 口语风格，不是改写来源。
SEEDS: dict[str, list[str]] = {
    "问答": ["断路器多久检修一次啊？", "电缆巡视都有啥讲究啊？", "变压器渗油的处理规程是啥？"],
    "状态查询": ["1号主变现在多少度？", "母线电压现在多少？", "断路器现在是合着还是断着？"],
    "异常处置": ["主变漏油了咋回事？", "这毛病算哪一档？", "开关柜里面滋滋响，帮我查查啥毛病？"],
    "工单生成": ["帮我在系统里派个活，安排人去处理", "这个缺陷开个单让人去修", "帮我记一下，安排人处理"],
    "其他": ["我家空调不制冷了怎么办？", "帮我写份工作总结", "变压器是干嘛用的啊？", "这系统收费吗？", "今天天气不错哈"],
}

# 每个意图的触发关键词（生成时禁用）。「异常处置」禁用词 = 原「告警/缺陷/诊断」三个旧类的
# 并集——规则层虽已合并，闭卷评测仍要保证口语不含这些触发词。
FORBID: dict[str, list[str]] = {
    "问答": ["规程", "标准", "依据", "处置", "规定", "规范", "条款", "导则"],
    "状态查询": ["温度", "电流", "电压", "量测", "台账", "状态"],
    "异常处置": ["缺陷", "分级", "定级", "等级", "告警", "报警", "诊断", "故障", "局放", "过热"],
    "工单生成": ["工单", "派单", "开单", "下单"],
    "其他": [],
}


def load_existing() -> list[dict]:
    if not OUT.exists():
        return []
    ns: dict = {}
    exec(OUT.read_text(encoding="utf-8"), ns)
    return list(ns.get("CLOSED_INTENT", []))


def _norm(text: str) -> str:
    """归一化用于去重：去标点/空格/语气词差异。"""
    return re.sub(r"[\s，。？！、,.!?～~的啊呀嘛呗吧啦了？]", "", text)


def generate_batch(llm: LLMClient, intent: str, forbid: list[str], existing_texts: list[str], k: int) -> list[str]:
    forbid_line = "、".join(f"「{w}」" for w in forbid) if forbid else "（无）"
    examples = "\n".join(f"- {s}" for s in SEEDS.get(intent, [])[:3])
    seen = "\n".join(f"- {t}" for t in existing_texts[:40])
    seen_block = f"\n【已有句子，绝对不要重复、不要换汤不换药】\n{seen}\n" if seen else ""

    prompt = (
        "你是电网运维专家。请模拟一线运维工人在值班室/巡检现场随口说的话，"
        f"生成 {k} 条【{intent}】意图的口语问句。\n\n"
        f"【这个意图是什么】{INTENT_DEFS[intent]}\n\n"
        "【硬性要求】\n"
        "1. 每条必须是短句一线口语，带口语词（咋/啥/啦/呗/吧/瞅瞅/整/多会儿），像真有人随口问。\n"
        f"2. 每条必须表达【{intent}】意图，不要跑偏成别的意图。\n"
        f"3. 禁用词：绝不能出现这些字词：{forbid_line}。\n"
        f"4. {k} 条之间必须互不相同，说法要多样（换设备、换场景、换问法、换口语词）。\n"
        "5. 不要照抄风格示例，只是参考语气。\n"
        "6. 只输出一个 JSON 数组，不要任何解释或代码块：[\"句子1\",\"句子2\",...]\n\n"
        f"【风格参考示例】\n{examples}\n"
        + seen_block
    )
    try:
        raw = llm.chat([{"role": "user", "content": prompt}], temperature=0.9).strip()
    except LLMError:
        return []
    # 容错解析：剥掉可能的 ```json 围栏
    if raw.startswith("```"):
        raw = raw.strip("`")
        if raw.lower().startswith("json"):
            raw = raw[4:]
        raw = raw.strip()
    try:
        arr = json.loads(raw)
    except json.JSONDecodeError:
        m = re.findall(r'"([^"]+)"', raw)
        arr = m
    out = []
    for s in arr:
        s = str(s).strip().strip("「」『』\"'")
        if s:
            out.append(s)
    return out


def _still_has_forbid(text: str, forbid: list[str]) -> list[str]:
    return [w for w in forbid if w in text]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--target-per-intent", type=int, default=20, help="每类目标条数")
    ap.add_argument("--batch", type=int, default=10, help="每轮生成条数")
    ap.add_argument("--intent", default=None, choices=INTENTS, help="只生成某一意图")
    ap.add_argument("--fresh", action="store_true", help="清空旧评测集重新生成")
    ap.add_argument("--max-rounds", type=int, default=30, help="每类最多生成轮数")
    args = ap.parse_args()

    if args.fresh:
        existing = load_existing()
        if args.intent:
            # 指定意图时：只替换该意图的旧条目，保留其他类
            existing = [r for r in existing if r["intent"] != args.intent]
        else:
            existing = []
    else:
        existing = load_existing()

    intents = [args.intent] if args.intent else INTENTS
    llm = LLMClient()

    rows: list[dict] = list(existing)
    # 已有句子集合（按归一化去重键）
    def keys_of(rows_: list[dict]) -> set[str]:
        return {_norm(r["text"]) for r in rows_}

    print(f"已有 {len(rows)} 条；目标每类 {args.target_per_intent} 条\n")

    for intent in intents:
        have = sum(1 for r in rows if r["intent"] == intent)
        need = args.target_per_intent - have
        if need <= 0:
            print(f"[{intent}] 已够 {have} 条，跳过")
            continue
        forbid = FORBID[intent]
        print(f"[{intent}] 现有 {have}，需补 {need} ...")
        stagnant = 0
        while need > 0 and stagnant < 3:
            keys = keys_of(rows)
            texts = generate_batch(llm, intent, forbid, [r["text"] for r in rows if r["intent"] == intent], min(args.batch, need + args.batch))
            added = 0
            for t in texts:
                if _norm(t) in keys:
                    continue  # 字面/归一化重复，跳过
                keys.add(_norm(t))
                rows.append({"text": t, "intent": intent, "src": "LLM 直接生成"})
                added += 1
            if added == 0:
                stagnant += 1
            else:
                stagnant = 0
                need -= added
            _write_out(rows)
            print(f"    本轮新增 {added}，累计 {sum(1 for r in rows if r['intent'] == intent)} 条（待补 {max(need,0)}）", flush=True)
        _write_out(rows)
        _write_review(rows)

    print(f"\n完成：合计 {len(rows)} 条")
    print(f"评测集：{OUT}")
    print(f"审核清单：{REVIEW}")
    print(f"token 用量：{llm.get_usage()}")


def _write_out(rows: list[dict]) -> None:
    header = (
        '"""闭卷口语意图评测集：LLM 直接生成（强制禁用触发关键词 + 强制不重复 + 去重），意图为自动标注，需 100% 人工审核。\n\n'
        "用途：评测意图识别在「不带触发关键词」的一线口语下的准确率（开卷用规范问句，会高估规则层）。\n"
        "text=口语问句；intent=自动标注意图；src=生成方式（供追溯）。\n"
        '"""\n\n'
        "CLOSED_INTENT = [\n"
    )
    body = ""
    for r in rows:
        body += (
            "    {\n"
            f"        \"text\": {r['text']!r},\n"
            f"        \"intent\": {r['intent']!r},\n"
            f"        \"src\": {r['src']!r},\n"
            "    },\n"
        )
    OUT.write_text(header + body + "]\n", encoding="utf-8")


def _write_review(rows: list[dict]) -> None:
    header = (
        "# 意图识别闭卷评测集 · 审核清单\n\n"
        "> text 是 LLM 生成的口语，intent 是自动标注。请逐条审核：text 是否仍表达同一意图（intent）；是否真的没带触发关键词。\n"
        "> 表达正确打 ✓；改错意图在「纠正」栏写正确意图或「删除」；仍带触发词的在「仍含触发词」栏标 ⚠️。\n\n"
    )
    by_intent: dict[str, list[dict]] = {}
    for r in rows:
        by_intent.setdefault(r["intent"], []).append(r)
    parts = [header]
    for intent in INTENTS:
        items = by_intent.get(intent, [])
        if not items:
            continue
        parts.append(f"## {intent}（{len(items)} 条）\n\n")
        parts.append("| # | 口语问句 text | 标注意图 | 仍含触发词 | ✓/✗ | 纠正 |\n")
        parts.append("|---|---|---|---|---|---|\n")
        for i, r in enumerate(items, 1):
            leaked = _still_has_forbid(r["text"], FORBID.get(intent, []))
            leak = "⚠️ " + "、".join(leaked) if leaked else ""
            parts.append(f"| {i} | {r['text']} | {r['intent']} | {leak} |  |  |\n")
        parts.append("\n")
    REVIEW.write_text("".join(parts), encoding="utf-8")


if __name__ == "__main__":
    main()
