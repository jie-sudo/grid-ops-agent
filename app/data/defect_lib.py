"""结构化缺陷库抽取：从缺陷分类标准文本解析出「设备类别×部件×部位×等级×缺陷内容」。

针对 Q/GDW 745 这类规整结构（章节号 → a/b/c 等级 → 数字条目）的纯函数解析器。
输入清洗后的正文，输出结构化记录列表，可单测、不依赖 DB/LLM。
"""
from __future__ import annotations

import re

_HEADING_RE = re.compile(r"^(\d+(?:\.\d+)*)\s+(.+)$")
_LEVEL_RE = re.compile(r"^([a-cA-C][)）])\s*(.+)$")
_ITEM_RE = re.compile(r"^(\d+[)）])\s*(.+)$")


def _cjk_bigrams(text: str) -> set[str]:
    """提取纯中文 bigram（排除数字/英文，避免数值阈值造成误匹配）。"""
    q = re.sub(r"[^一-鿿]+", "", text or "")
    return {q[i : i + 2] for i in range(len(q) - 1)}


def _norm_level(s: str) -> str:
    for k in ("危急", "严重", "一般"):
        if k in s:
            return k
    return s.strip()


def parse_defect_library(text: str) -> list[dict]:
    """解析缺陷分类标准正文 → 缺陷库记录。

    层级：4.1（设备类别）→ 4.1.1（部件）→ 4.1.1.1（部位）→ a/b/c（等级）→ 数字条目（缺陷内容）。
    条目跨行（OCR 断行）会累积到同一记录。
    """
    records: list[dict] = []
    cat = comp = part = level = ""
    cur_item = ""

    def flush() -> None:
        nonlocal cur_item
        # 只需等级 + 缺陷内容；类别/部件/部位都是可选上下文（如 4.5 跌落式熔断器直接 类别→等级→条目）
        if cur_item and level:
            records.append({
                "device_category": cat,
                "component": comp,
                "part": part,
                "level": level,
                "defect": cur_item,
            })
        cur_item = ""

    for line in text.splitlines():
        s = line.strip()
        if not s:
            continue
        if s.startswith("附录") or "规范性附录" in s or "资料性附录" in s or s.startswith("参考文献"):
            break  # 附录/参考文献之后是汇总表格，不是缺陷条目
        hm = _HEADING_RE.match(s)
        if hm:
            depth = hm.group(1).count(".")
            title = f"{hm.group(1)} {hm.group(2)}"
            if depth == 1:
                flush()
                cat, comp, part = title, "", ""
            elif depth == 2:
                flush()
                comp, part = title, ""
            elif depth == 3:
                flush()
                part = title
            continue
        lm = _LEVEL_RE.match(s)
        if lm:
            flush()
            level = _norm_level(lm.group(2))
            continue
        im = _ITEM_RE.match(s)
        if im:
            flush()
            cur_item = im.group(2).strip()
            continue
        if cur_item:  # 续行（条目被 OCR 断行）
            cur_item += s
    flush()
    return records


def match_defect_library(description: str, records: list[dict], threshold: float = 0.7, device_type: str | None = None):
    """在缺陷库记录中匹配描述，返回 (level, record) 或 (None, None)。

    安全原则：只有匹配到「单一等级」时才定级；匹配到多个等级（歧义）或 0 个 → 不定级。
    device_type：设备粗类关键词（如"变压器/断路器/开关柜"），有值时优先在匹配设备的记录里
    定级（子串匹配设备字段），减少跨设备歧义；匹配不到则回退全库（保守）。
    threshold 取 0.7（保守）：要求 ≥70% 的描述 bigram 命中，避免相似但不同等级的记录误匹配。
    """
    return match_by_bigram(description, records, threshold=threshold, device_type=device_type)


def match_by_bigram(description: str, records: list[dict], threshold: float = 0.7, device_type: str | None = None):
    """字符 bigram 字面匹配（纯函数，不依赖模型）。"""
    terms = _cjk_bigrams(description)
    if not terms:
        return None, None
    # 设备类型筛选：有 device_type 时，先按设备字段子串过滤；过滤结果非空才用，否则回退全库
    if device_type:
        filtered = [
            r for r in records
            if device_type in (
                (r.get("device_type") or "") + (r.get("device_category") or "")
                + (r.get("device_kind") or "") + (r.get("component") or "")
            )
        ]
        if filtered:
            records = filtered
    matched_levels: set[str] = set()
    best = None
    best_score = 0.0
    for rec in records:
        # 纳入 basis（分类依据）：1906 库同一"缺陷描述"靠"分类依据"区分等级
        hay = " ".join([
            rec.get("component", ""), rec.get("part", ""),
            rec.get("defect", ""), rec.get("basis", ""),
        ])
        score = sum(1 for t in terms if t in hay) / len(terms)
        if score >= threshold:
            matched_levels.add(rec.get("level"))
            if score > best_score:
                best_score, best = score, rec
    if len(matched_levels) == 1 and best is not None:
        return best.get("level"), best
    return None, None
