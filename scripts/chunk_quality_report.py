"""切分质量报告：对全部资料做「清洗 + 结构切分」，输出结构性指标，判断"切分切好没"。

用法（SAM2 环境）：
    python scripts/chunk_quality_report.py --skip-pdf   # 只看 OCR txt
    python scripts/chunk_quality_report.py              # 含文字版 PDF

输出的指标含义：
- 块 / 均长 / 最长：块数和长度分布（太碎 or 太长都不好）
- 路径%：带章节路径的块占比（越高说明结构切分越生效，没结构的文档会低，正常）
- 孤儿：只有标题没正文的块（应为 0）
- 超长：超过 size 被硬切的块（越少越好，说明章节大小合适）
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.data.kb import chunk_metrics, chunk_structured
from app.data.ocr_clean import clean_ocr_text

MATERIAL_DIR = Path(__file__).resolve().parents[2] / "资料"
OCR_DIR = MATERIAL_DIR / "ocr_text"


def pdf_text(pdf_path: Path) -> str:
    import fitz
    doc = fitz.open(str(pdf_path))
    text = "\n".join(f"===== 第 {i + 1} 页 =====\n" + (doc[i].get_text() or "") for i in range(len(doc)))
    doc.close()
    return text


def collect() -> list[tuple[str, str]]:
    sources = []
    if OCR_DIR.exists():
        for p in sorted(OCR_DIR.glob("*.txt")):
            sources.append((p.stem, p.read_text(encoding="utf-8")))
    try:
        import fitz
        for p in sorted(MATERIAL_DIR.glob("*.pdf")):
            try:
                doc = fitz.open(str(p))
                chars = sum(len((doc[i].get_text() or "")) for i in range(min(3, len(doc))))
                doc.close()
                if chars >= 80:
                    sources.append((p.stem, pdf_text(p)))
            except Exception:
                continue
    except ImportError:
        pass
    return sources


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--skip-pdf", action="store_true")
    args = ap.parse_args()

    rows = []
    for stem, raw in collect():
        if args.skip_pdf is False and stem.endswith((" (1)", " (2)")):
            continue
        clean = clean_ocr_text(raw)
        if not clean.strip():
            continue
        m = chunk_metrics(chunk_structured(clean))
        rows.append((stem, m))

    print(f"{'文件':<42}{'块':>5}{'均长':>7}{'路径%':>6}{'孤儿':>5}{'>500':>6}")
    tot = {"chunks": 0, "orphan": 0, "over": 0, "hdr": 0}
    for stem, m in rows:
        print(f"{stem[:41]:<42}{m['chunks']:>5}{m['avg_len']:>7.0f}{m['with_header_ratio']*100:>5.0f}%{m['orphan']:>5}{m['over_embed']:>6}")
        tot["chunks"] += m["chunks"]
        tot["orphan"] += m["orphan"]
        tot["over"] += m["over_embed"]
        tot["hdr"] += round(m["with_header_ratio"] * m["chunks"])
    n = tot["chunks"]
    print("-" * 70)
    if n:
        print(f"合计 {len(rows)} 篇 {n} 块 | 孤儿 {tot['orphan']} | 超过嵌入上限(>500字) {tot['over']} | 带路径 {tot['hdr']}/{n} ({round(tot['hdr']/n*100,1)}%)")
    else:
        print("无数据")


if __name__ == "__main__":
    main()
