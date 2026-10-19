"""扫描件批量 OCR（PaddleOCR，中文电网技术文档）。

把「资料」目录里的扫描版 PDF 逐页渲染成图片 → PaddleOCR 识别 → 输出纯文本，
供后续切分入库。文字版 PDF 自动跳过（不用 OCR）。

用法（在 SAM2 环境）：
    先装依赖：pip install -i https://pypi.tuna.tsinghua.edu.cn/simple paddlepaddle paddleocr pymupdf

    冒烟测试（只跑 1 页，先验证环境）：
        python scripts/ocr_pdfs.py --test-one

    全量跑（--scale 越小越快，默认 2.0，赶时间可降到 1.5）：
        python scripts/ocr_pdfs.py --dir "F:\\通用agent\\资料" --out "F:\\通用agent\\资料\\ocr_text" --scale 1.5

    断点续跑（跳过已产出的 txt）：
        python scripts/ocr_pdfs.py --dir ... --out ... --skip-existing
"""
from __future__ import annotations

import argparse
import os
import sys
import tempfile
import warnings
from pathlib import Path

warnings.filterwarnings("ignore")
# 压低 Paddle/glog 日志：ReduceMeanCheckIfOneDNNSupport 这类 oneDNN 调试信息会刷屏
os.environ.setdefault("GLOG_minloglevel", "2")  # 只留 ERROR 以上
os.environ.setdefault("FLAGS_v", "0")           # 关 VLOG 详细日志

DEFAULT_DIR = Path(__file__).resolve().parents[2] / "资料"
DEFAULT_OUT = DEFAULT_DIR / "ocr_text"


def make_ocr():
    """加载 PaddleOCR，兼容 2.x / 3.x 两种构造参数。"""
    try:
        from paddleocr import PaddleOCR
    except ImportError:
        sys.exit("未安装 paddleocr。请先：pip install -i https://pypi.tuna.tsinghua.edu.cn/simple paddlepaddle paddleocr pymupdf")
    try:
        # 2.x 参数
        return PaddleOCR(use_angle_cls=True, lang="ch", show_log=False)
    except (TypeError, ValueError):
        # 3.x：show_log 等旧参数会抛 ValueError（不是 TypeError）
        # 开 oneDNN 提速；要求 paddlepaddle<=3.2.1（3.3.0+ 有 PIR+oneDNN 已知 bug：
        #   ConvertPirAttribute2RuntimeAttribute not support pir::ArrayAttribute<pir::DoubleAttribute>）
        # small 档比默认 medium 快 2~4 倍，打印体规程够用；tiny 更快但小字易丢
        return PaddleOCR(lang="ch",
                         text_detection_model_name="PP-OCRv6_small_det",
                         text_recognition_model_name="PP-OCRv6_small_rec",
                         use_doc_orientation_classify=False,
                         use_doc_unwarping=False, use_textline_orientation=False,
                         enable_mkldnn=True)


def ocr_image(ocr, img_path: str) -> list[str]:
    """识别单张图片，返回按行文本（兼容 PaddleOCR 2.x / 3.x 返回结构）。"""
    if hasattr(ocr, "predict"):
        res = ocr.predict(img_path)
        lines: list[str] = []
        for page in res or []:
            if isinstance(page, dict) and "rec_texts" in page:
                lines.extend(page["rec_texts"])
            elif isinstance(page, str):
                lines.append(page)
        return lines
    else:
        res = ocr.ocr(img_path, cls=True)
        lines = []
        if res and res[0]:
            for line in res[0]:
                if isinstance(line, (list, tuple)) and len(line) >= 2 and line[1]:
                    text = line[1][0] if isinstance(line[1], (list, tuple)) else str(line[1])
                    lines.append(text)
        return lines


def is_scanned(pdf_path: str, check_pages: int = 3) -> bool:
    """前几页抽不到文字 → 视为扫描件。"""
    import fitz  # PyMuPDF
    doc = fitz.open(pdf_path)
    chars = 0
    for i in range(min(check_pages, len(doc))):
        chars += len(doc[i].get_text() or "")
    doc.close()
    return chars < 80


def ocr_pdf(ocr, pdf_path: Path, out_path: Path, scale: float = 2.0) -> int:
    import fitz
    doc = fitz.open(str(pdf_path))
    parts: list[str] = []
    with tempfile.TemporaryDirectory() as tmp:
        for i, page in enumerate(doc):
            pix = page.get_pixmap(matrix=fitz.Matrix(scale, scale))  # 缩放越大越慢越准
            img_path = Path(tmp) / f"p{i}.png"
            pix.save(str(img_path))
            try:
                lines = ocr_image(ocr, str(img_path))
            except Exception as e:
                lines = [f"[OCR失败: {e}]"]
            parts.append(f"===== 第 {i + 1} 页 =====\n" + "\n".join(lines))
    doc.close()
    out_path.write_text("\n".join(parts), encoding="utf-8")
    return len(parts)


def test_one(ocr, data_dir: Path, scale: float = 2.0) -> None:
    """冒烟测试：随便挑一个扫描件，只 OCR 第 1 页，打印结果。"""
    scanned = [p for p in data_dir.glob("*.pdf") if is_scanned(str(p))]
    if not scanned:
        print("没找到扫描件（可能全是文字版）。")
        return
    target = scanned[0]
    print(f"测试文件：{target.name}")
    import fitz
    doc = fitz.open(str(target))
    pix = doc[0].get_pixmap(matrix=fitz.Matrix(scale, scale))
    with tempfile.TemporaryDirectory() as tmp:
        img = Path(tmp) / "test.png"
        pix.save(str(img))
        lines = ocr_image(ocr, str(img))
    doc.close()
    print(f"第 1 页识别结果（{len(lines)} 行）：")
    print("\n".join(lines[:40]))


def main() -> None:
    ap = argparse.ArgumentParser(description="扫描 PDF 批量 OCR（PaddleOCR）")
    ap.add_argument("--dir", default=str(DEFAULT_DIR), help="PDF 目录")
    ap.add_argument("--out", default=str(DEFAULT_OUT), help="输出文本目录")
    ap.add_argument("--skip-existing", action="store_true", help="跳过已有 txt")
    ap.add_argument("--limit", type=int, default=0, help="最多处理 N 个文件（0=全部）")
    ap.add_argument("--test-one", action="store_true", help="冒烟测试：只跑 1 页")
    ap.add_argument("--scale", type=float, default=2.0, help="渲染缩放倍数（1.5 更快，2.0 更准）")
    args = ap.parse_args()

    data_dir = Path(args.dir)
    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)

    print("加载 PaddleOCR（首次会下载模型，稍等）...")
    ocr = make_ocr()

    if args.test_one:
        test_one(ocr, data_dir, scale=args.scale)
        return

    # 只挑扫描件
    pdfs = [p for p in data_dir.glob("*.pdf") if is_scanned(str(p))]
    print(f"发现扫描件 {len(pdfs)} 个（文字版已跳过）")

    done = 0
    for idx, pdf in enumerate(pdfs, 1):
        out_txt = out_dir / (pdf.stem + ".txt")
        if args.skip_existing and out_txt.exists():
            print(f"[{idx}/{len(pdfs)}] 跳过（已存在） {pdf.name}")
            continue
        print(f"[{idx}/{len(pdfs)}] OCR 中... {pdf.name}", flush=True)
        pages = ocr_pdf(ocr, pdf, out_txt, scale=args.scale)
        print(f"    -> {pages} 页 -> {out_txt.name}")
        done += 1
        if args.limit and done >= args.limit:
            print(f"达到 --limit={args.limit}，停止。")
            break

    print(f"完成，处理 {done} 个文件，输出到 {out_dir}")


if __name__ == "__main__":
    main()
