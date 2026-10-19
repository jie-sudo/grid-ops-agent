"""OCR/PDF 资料清洗 + 切分 + 入库（ChromaDB）。

用法（SAM2 环境，先确认 ChromaDB 已起）：
    python scripts/ingest_ocr_kb.py --dry-run      # 先预览：每个文件切出多少 chunk、不写库
    python scripts/ingest_ocr_kb.py                 # 正式入库

- 读 资料/ocr_text/*.txt（OCR 结果）+ 资料/*.pdf 里的文字版，做清洗；
- 清洗 → 切分 → 灌 ChromaDB（collection "knowledge"，与 34 篇规程同库同格式）。
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.config import get_settings
from app.data.kb import chunk_structured, infer_domain
from app.data.ocr_clean import clean_ocr_text
from app.data.vectorstore import VectorStore

MATERIAL_DIR = Path(__file__).resolve().parents[2] / "资料"
OCR_DIR = MATERIAL_DIR / "ocr_text"

_STD_RE = re.compile(r"([A-Za-z][A-Za-z0-9_/∕／.\s-]*?\d{4})")


def extract_std_no(stem: str) -> str:
    m = _STD_RE.match(stem)
    if not m:
        return ""
    code = m.group(1).strip()
    code = code.replace("／", "/").replace("∕", "/").replace("_", "/")
    return re.sub(r"\s+", " ", code).strip()


def extract_year(stem: str) -> str:
    m = re.search(r"(19|20)\d{2}", stem)
    return m.group(0) if m else ""


def infer_doc_type(stem: str) -> str:
    if "缺陷分类标准" in stem:
        return "缺陷分类标准"
    if "导则" in stem:
        return "导则"
    if "规程" in stem:
        return "规程"
    if "案例" in stem or "故障" in stem:
        return "案例"
    if "作业指导书" in stem:
        return "作业指导书"
    if "安规" in stem or "安全工器具" in stem:
        return "安全规程"
    if "运行规程" in stem:
        return "运行规程"
    if "标准" in stem:
        return "标准"
    return "资料"


def pdf_text_with_pages(pdf_path: Path) -> str:
    import fitz
    doc = fitz.open(str(pdf_path))
    parts = [f"===== 第 {i + 1} 页 =====\n" + (doc[i].get_text() or "") for i in range(len(doc))]
    doc.close()
    return "\n".join(parts)


def collect_sources() -> list[tuple[str, str]]:
    sources: list[tuple[str, str]] = []
    if OCR_DIR.exists():
        for p in sorted(OCR_DIR.glob("*.txt")):
            sources.append((p.stem, p.read_text(encoding="utf-8")))
    import fitz
    for p in sorted(MATERIAL_DIR.glob("*.pdf")):
        try:
            doc = fitz.open(str(p))
            chars = sum(len((doc[i].get_text() or "")) for i in range(min(3, len(doc))))
            doc.close()
        except Exception:
            continue
        if chars >= 80:  # 文字版 PDF
            sources.append((p.stem, pdf_text_with_pages(p)))
    return sources


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true", help="只统计不写库")
    args = ap.parse_args()

    sources = collect_sources()
    print(f"待入库 {len(sources)} 个文件")

    store = None
    if not args.dry_run:
        settings = get_settings()
        store = VectorStore(host=settings.chroma_host, port=settings.chroma_port)

    total_docs = total_chunks = 0
    for stem, raw in sources:
        # 跳过带 "(1)"/"(2)" 的重复文件（同名都有不带后缀的版本）
        if stem.endswith(" (1)") or stem.endswith(" (2)"):
            print(f"  跳过（重复） {stem}")
            continue
        clean = clean_ocr_text(raw)
        if not clean.strip():
            print(f"  跳过（清洗后为空） {stem}")
            continue
        chunks = chunk_structured(clean)
        if args.dry_run:
            print(f"  {len(chunks):>4} chunks  {stem}")
            total_docs += 1
            total_chunks += len(chunks)
            continue

        try:
            store.collection.delete(where={"title": stem})
        except Exception:
            pass
        meta = {
            "title": stem,
            "source": extract_std_no(stem),
            "device_domain": infer_domain(stem, clean),
            "doc_type": infer_doc_type(stem),
            "status": "active",
            "version": extract_year(stem),
            "effective_date": extract_year(stem),
            "superseded_by": "",
        }
        ids = [f"{stem}-{i}" for i in range(len(chunks))]
        store.add(ids, chunks, [dict(meta) for _ in chunks])
        total_docs += 1
        total_chunks += len(chunks)
        print(f"  {len(chunks):>4} chunks  {stem}  [{meta['source'] or '无标准号'} / {meta['device_domain']} / {meta['doc_type']}]")

    suffix = "（dry-run，未写库）" if args.dry_run else ""
    print(f"完成：{total_docs} 篇，{total_chunks} chunks{suffix}")


if __name__ == "__main__":
    main()
