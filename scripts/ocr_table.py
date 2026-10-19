"""表格 OCR（PP-StructureV3）：识别扫描件里的表格，输出结构化 HTML。

针对 Q/GDW 1906 这类"表 A.1 标准缺陷库"（合并单元格的复杂表），普通文本 OCR
会把行列打碎，PP-Structure 走"版面分析 + 表格结构识别"，输出单元格对齐的 HTML。

用法（SAM2 环境）：
    冒烟测试（只跑 1 页，验证 PP-StructureV3 装没装、表格识别质量）：
        python scripts/ocr_table.py --test-one --src "F:\\通用agent\\资料\\Q_GDW 1906-2013 输变电一次设备缺陷分类标准 - 副本.pdf"

    全量（先跑通冒烟再上）：
        python scripts/ocr_table.py --src <pdf> --out <目录> --pages 1-20
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import tempfile
import warnings
from pathlib import Path

warnings.filterwarnings("ignore")
os.environ.setdefault("GLOG_minloglevel", "2")
os.environ.setdefault("FLAGS_v", "0")

DEFAULT_SRC = (
    Path(__file__).resolve().parents[2]
    / "资料"
    / "Q_GDW 1906-2013 输变电一次设备缺陷分类标准 - 副本.pdf"
)
DEFAULT_OUT = Path(__file__).resolve().parents[2] / "资料" / "table_html"


def make_structure():
    """加载表格识别管线，优先 PPStructureV3，降级 PPStructure。"""
    try:
        from paddleocr import PPStructureV3
    except ImportError:
        PPStructureV3 = None
    if PPStructureV3 is not None:
        try:
            return PPStructureV3(
                text_detection_model_name="PP-OCRv6_small_det",
                text_recognition_model_name="PP-OCRv6_small_rec",
                use_doc_orientation_classify=False,
                use_doc_unwarping=False,
                use_textline_orientation=False,
                enable_mkldnn=True,
            )
        except Exception:
            pass
    from paddleocr import PPStructure

    return PPStructure(show_log=False)


def render_page(pdf_path: Path, page_idx: int, scale: float, tmp: Path) -> Path:
    import fitz

    doc = fitz.open(str(pdf_path))
    pix = doc[page_idx].get_pixmap(matrix=fitz.Matrix(scale, scale))
    doc.close()
    img = tmp / f"p{page_idx}.png"
    pix.save(str(img))
    return img


def extract_html(result) -> list[str]:
    """从 PP-Structure 结果里尽量提取表格 HTML（兼容 V3 / 旧版两种结构）。"""
    htmls: list[str] = []
    items = result if isinstance(result, list) else [result]
    for item in items:
        if not item:
            continue
        if hasattr(item, "res"):
            item = item.res
        if not isinstance(item, dict):
            continue
        # V3：table_res_list 里每个 dict 带 html
        for t in item.get("table_res_list") or []:
            if isinstance(t, dict) and t.get("html"):
                htmls.append(t["html"])
        # 旧版：顶层 type == 'table'，res 里带 html
        if item.get("type") == "table" and isinstance(item.get("res"), dict):
            h = item["res"].get("html") or ""
            if h:
                htmls.append(h)
    return htmls


def test_one(pipeline, pdf_path: Path, scale: float) -> None:
    print(f"测试文件：{pdf_path.name}")
    # 找第一页有表格的（跳过封面/目录，从第 5 页起找）
    with tempfile.TemporaryDirectory() as tmp:
        tmpd = Path(tmp)
        for page_idx in range(5, 30):
            img = render_page(pdf_path, page_idx, scale, tmpd)
            try:
                result = pipeline.predict(str(img))
            except TypeError:
                result = pipeline(str(img))
            htmls = extract_html(result)
            if htmls:
                print(f"第 {page_idx + 1} 页识别到 {len(htmls)} 个表格，第一个表格 HTML：")
                print(htmls[0][:2000])
                return
            # 没识别到表格，dump 原始结构供调试
            if page_idx == 5:
                print("第 6 页原始结果结构（供调试）：")
                print(json.dumps(result, ensure_ascii=False, default=str)[:1500])
    print("前 30 页没识别到表格，可能需要调整。")


def parse_pages(s: str | None):
    if not s:
        return None
    a, _, b = s.partition("-")
    return (int(a) - 1, int(b) - 1 if b else int(a) - 1)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--src", default=str(DEFAULT_SRC))
    ap.add_argument("--out", default=str(DEFAULT_OUT))
    ap.add_argument("--pages", default=None, help="页范围，如 1-20（1 起）")
    ap.add_argument("--scale", type=float, default=2.0)
    ap.add_argument("--test-one", action="store_true")
    args = ap.parse_args()

    src = Path(args.src)
    print("加载 PP-Structure（首次会下载版面/表格模型，稍等）...")
    pipeline = make_structure()

    if args.test_one:
        test_one(pipeline, src, args.scale)
        return

    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)
    lo, hi = parse_pages(args.pages) if args.pages else (0, None)

    import fitz

    doc = fitz.open(str(src))
    n = len(doc)
    hi = hi if hi is not None else n - 1
    hi = min(hi, n - 1)
    print(f"共 {n} 页，处理 {lo + 1}~{hi + 1}")

    with tempfile.TemporaryDirectory() as tmp:
        tmpd = Path(tmp)
        for i in range(lo, hi + 1):
            img = render_page(src, i, args.scale, tmpd)
            try:
                result = pipeline.predict(str(img))
            except TypeError:
                result = pipeline(str(img))
            htmls = extract_html(result)
            if htmls:
                out = out_dir / f"{src.stem}_p{i + 1}.html"
                out.write_text("\n\n".join(htmls), encoding="utf-8")
                print(f"[{i + 1}/{n}] {len(htmls)} 个表格 -> {out.name}")
            else:
                print(f"[{i + 1}/{n}] 无表格")
    doc.close()
    print(f"完成，HTML 输出到 {out_dir}")


if __name__ == "__main__":
    main()
