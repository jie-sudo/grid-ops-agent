"""知识库语料工具：解析 front matter、设备域推断、切片（纯函数，可单测）。"""
from __future__ import annotations

import re
from pathlib import Path

DOMAIN_KEYWORDS = {
    "变压器": ["变压器", "油浸式", "分接开关", "绕组"],
    "开关柜": ["开关柜", "GIS", "断路器", "操动机构", "五防"],
    "电缆": ["电缆", "护层", "电缆附件"],
    "线路": ["线路", "架空", "杆塔", "污区", "爬电"],
    "继电保护": ["继保", "继电保护", "整定", "故障录波"],
}


def parse_doc(path: Path) -> tuple[dict, str, str]:
    """解析 .md 文档 → (front matter, 标题, 正文)。"""
    text = path.read_text(encoding="utf-8")
    fm: dict[str, str] = {}
    body = text
    m = re.match(r"^---\n(.*?)\n---\n", text, re.S)
    if m:
        for line in m.group(1).splitlines():
            if ":" in line:
                k, _, v = line.partition(":")
                fm[k.strip()] = v.strip().strip('"')
        body = text[m.end():]
    title = path.stem.split("-", 1)[-1] if "-" in path.stem else path.stem
    return fm, title, body


def infer_domain(title: str, body: str) -> str:
    text = title + body[:200]
    for domain, kws in DOMAIN_KEYWORDS.items():
        for kw in kws:
            if kw in text:
                return domain
    return "通用"


def chunk_text(text: str, size: int = 600) -> list[str]:
    """按段落聚合为 chunk（约 size 字符）。"""
    paras = [p.strip() for p in text.split("\n") if p.strip()]
    chunks: list[str] = []
    cur = ""
    for p in paras:
        if cur and len(cur) + len(p) + 1 > size:
            chunks.append(cur)
            cur = p
        else:
            cur = f"{cur}\n{p}" if cur else p
    if cur:
        chunks.append(cur)
    return chunks


# 结构感知切分：识别标准/导则的章节、等级、无编号章节
_HEADING_RE = re.compile(r"^(\d+(?:\.\d+)*)\s+(.+)$")  # 4.1.1.1 杆塔本体
_LEVEL_RE = re.compile(r"^([a-cA-C][)）])\s*(.*)$")  # a）危急缺陷 / a) 危急缺陷
_SECTION_RE = re.compile(r"^(前言|引言|范围|术语和定义|规范性引用文件|目次|目录)$")


def chunk_structured(text: str, size: int = 400) -> list[str]:
    """结构感知切分：章节硬边界 + 等级软边界，块长控制在嵌入模型上限内。

    默认 size=400：BAAI/bge-small-zh-v1.5 的 max_seq_length=512 token（中文约 500 字），
    块头（章节路径）约 100 字，正文 ≤400 字保证不超嵌入上限、不被静默截断。
    等级（a）危急）在块较大时作为软边界切分，避免危急/严重/一般混在同一块里硬拆。
    """
    lines = [l.strip() for l in text.splitlines() if l.strip()]
    chunks: list[str] = []
    cur: list[str] = []
    path: list[str] = []

    def _depth(num: str) -> int:
        return num.count(".")

    def emit() -> None:
        if cur:
            header = " / ".join(path) if path else ""
            body = "\n".join(cur)
            chunks.append(f"{header}\n{body}" if header else body)
            cur.clear()

    for line in lines:
        hm = _HEADING_RE.match(line)
        if hm:
            emit()
            path = path[: _depth(hm.group(1))] + [line]
        elif _SECTION_RE.match(line):
            emit()
            path = [line]
        elif _LEVEL_RE.match(line) and cur and sum(len(x) for x in cur) >= size * 0.5:
            # 等级软边界：当前块已较大且遇到新等级，从等级处切
            emit()
            cur = [line]
        elif cur and sum(len(x) for x in cur) + len(line) + 1 > size:
            emit()
            cur = [line]
        else:
            cur.append(line)
    emit()
    return chunks


def chunk_metrics(chunks: list[str], size: int = 400) -> dict:
    """切分质量的结构性指标（纯函数，可单测）。

    - chunks: 块数
    - avg_len / min_len / max_len: 块长度（字符）
    - with_header_ratio: 带章节路径的块占比（结构切分生效程度，越高越好）
    - orphan: 孤儿块数（只有标题没正文，应为 0）
    - over_size: 超长块数（章节超大被硬切的，越少越好）
    """
    n = len(chunks)
    lens = [len(c) for c in chunks]
    with_header = 0
    orphan = 0
    for c in chunks:
        lines = c.split("\n")
        first = lines[0].strip() if lines else ""
        if " / " in first or _HEADING_RE.match(first) or _SECTION_RE.match(first):
            with_header += 1
        body = [l for l in lines if l.strip() and not (_HEADING_RE.match(l.strip()) or _SECTION_RE.match(l.strip()))]
        if not body:
            orphan += 1
    return {
        "chunks": n,
        "avg_len": round(sum(lens) / n, 1) if n else 0,
        "min_len": min(lens) if n else 0,
        "max_len": max(lens) if n else 0,
        "with_header_ratio": round(with_header / n, 3) if n else 0,
        "orphan": orphan,
        # 超过嵌入上限（bge-small-zh 512 token ≈ 500 字）会被静默截断，这是真正的风险指标
        "over_embed": sum(1 for l in lens if l > 500),
    }
