"""OCR 文本清洗（纯函数，可单测）。

把 PaddleOCR 产出的原始 txt（带"===== 第 N 页 ====="分隔）清洗成干净正文：
- 整页丢弃：知识星球广告页、封面/版权页、目次页
- 逐行丢弃：页眉（跨页重复的短行）、页码（纯数字/罗马数字）、乱码行（非常见字符占比过高）
"""
from __future__ import annotations

import re

PAGE_RE = re.compile(r"===== 第 (\d+) 页 =====")

# 知识星球广告页关键词（整页丢弃，需强特征，避免误伤正文）
AD_PAGE_KEYWORDS = (
    "长按", "二维码", "独家精华", "已有9999", "上万份", "资源合集",
)
# 知识星球水印行（逐行丢弃——"电力图书馆知识星球"等会出现在每页，不能整页丢）
WATERMARK_LINE_KEYWORDS = ("星球", "图书馆", "知识星球")
# 封面/版权页关键词
COVER_KEYWORDS = ("ICS", "备案号", "图书在版编目", "出版发行", "版 次", "印 张")

# 常见可接受字符（用于乱码率计算）
_EXTRA_OK = "，。、；：（）《》【】\"\"''‘’%℃≤≥×±～—-…·/\\,;:()[]%°~≥≤<>＝=!?！？·—…丨"


def split_pages(text: str) -> list[tuple[int, str]]:
    """按"===== 第 N 页 ====="切成 [(页码, 页文本), ...]（页文本已去首尾空白）。"""
    parts = PAGE_RE.split(text)
    pages = []
    for i in range(1, len(parts), 2):
        pages.append((int(parts[i]), parts[i + 1].strip()))
    return pages


def is_ad_page(page: str) -> bool:
    return any(kw in page for kw in AD_PAGE_KEYWORDS)


def is_cover_toc_page(page: str) -> bool:
    # 封面/版权页：短 + 含 ICS/备案号/出版发行等
    if len(page.strip()) < 600 and any(kw in page for kw in COVER_KEYWORDS):
        return True
    # 目次页：含"目次/目录" + 点点点引导
    if ("目次" in page or "目录" in page) and ("……" in page or "…" in page):
        return True
    # 目次页（OCR 常把"目次"竖排成"次/目"，靠大量点号引导识别）
    if page.count("…") >= 6:
        return True
    return False


def garbled_ratio(line: str) -> float:
    """非常见字符占比（>阈值视为乱码行）。"""
    if not line:
        return 0.0
    bad = 0
    for ch in line:
        if "一" <= ch <= "鿿" or ch.isalnum() or ch.isspace():
            continue
        if ch in _EXTRA_OK:
            continue
        bad += 1
    return bad / len(line)


def is_page_number(line: str) -> bool:
    s = line.strip()
    return bool(re.fullmatch(r"\d{1,3}", s)) or bool(re.fullmatch(r"[IVXivx]{1,5}", s))


def has_cjk(s: str) -> bool:
    return any("一" <= ch <= "鿿" for ch in s)


def is_garbled(line: str) -> bool:
    """判断是否为 OCR 乱码行。"""
    if len(line) < 3:
        return False
    # 含非 ASCII 的非常见字符（如 É é 等）
    if garbled_ratio(line) > 0.3:
        return True
    # 整行无中文 + 含 ≥3 连续字母 → 疑似英文/乱码（中文文档里英文标题价值低）
    if len(line) >= 6 and not has_cjk(line) and re.search(r"[A-Za-z]{3,}", line):
        return True
    return False


def clean_ocr_text(raw: str) -> str:
    """清洗整篇 OCR 文本，返回干净正文（页与页之间用空行分隔）。"""
    pages = split_pages(raw)
    if not pages:
        # 没有分页标记（比如直接抽文字的 PDF），按整篇处理
        pages = [(1, raw)]

    # 第一遍：统计短行出现次数（页眉/页脚通常每页都出现）
    header_counts: dict[str, int] = {}
    for _, page in pages:
        if is_ad_page(page) or is_cover_toc_page(page):
            continue
        for line in page.splitlines():
            s = line.strip()
            # 页眉通常是标准号（无中文）；"a）危急缺陷"这类有中文的重复行是正文，不能当页眉
            if s and len(s) <= 60 and not has_cjk(s):
                header_counts[s] = header_counts.get(s, 0) + 1

    kept: list[str] = []
    for _, page in pages:
        if is_ad_page(page) or is_cover_toc_page(page):
            continue
        lines = []
        for line in page.splitlines():
            s = line.strip()
            if not s:
                continue
            if any(kw in s for kw in WATERMARK_LINE_KEYWORDS):
                continue  # 水印行（如"电力图书馆知识星球"）
            if is_page_number(s):
                continue
            # 页眉：无中文的短行且跨 ≥3 页重复
            if len(s) <= 60 and not has_cjk(s) and header_counts.get(s, 0) >= 3:
                continue
            # 乱码行
            if is_garbled(s):
                continue
            lines.append(s)
        if lines:
            kept.append("\n".join(lines))
    return "\n\n".join(kept)
