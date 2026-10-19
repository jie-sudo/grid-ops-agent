"""商用表格 OCR（百度智能云「表格文字识别」）——针对扫描件复杂表格，输出单元格结构。

相比本地 PaddleOCR：百度表格识别对合并单元格、扫描件表格的识别质量高一个量级，
返回的是"单元格 + 行列坐标"，能直接重建结构化表格，而不是打碎的文本。

用法：
    1. 去百度智能云控制台（cloud.baidu.com）开通「表格文字识别」，拿到 API Key / Secret Key
    2. 设环境变量（或写进 .env，别提交）：
           set BAIDU_OCR_AK=你的AK
           set BAIDU_OCR_SK=你的SK
    3. 冒烟测试（只跑 1 页，验证 key 和接口）：
           python scripts/ocr_table_baidu.py --test-one --src "F:\\通用agent\\资料\\Q_GDW 1906-2013 输变电一次设备缺陷分类标准 - 副本.pdf"

    4. 全量（按页跑，输出每个表格页的 JSON + 重建的 CSV/HTML）：
           python scripts/ocr_table_baidu.py --src <pdf> --pages 1-20 --out <目录>

计费：表格文字识别按次（张图）计费，约几厘/张，358 页全量约几块钱。
"""
from __future__ import annotations

import argparse
import base64
import json
import os
import sys
import tempfile
from pathlib import Path

import httpx

DEFAULT_SRC = (
    Path(__file__).resolve().parents[2]
    / "资料"
    / "Q_GDW 1906-2013 输变电一次设备缺陷分类标准 - 副本.pdf"
)
DEFAULT_OUT = Path(__file__).resolve().parents[2] / "资料" / "table_json"

TOKEN_URL = "https://aip.baidubce.com/oauth/2.0/token"
TABLE_URL = "https://aip.baidubce.com/rest/2.0/ocr/v1/table"


def get_access_token(ak: str, sk: str) -> str:
    r = httpx.post(TOKEN_URL, params={
        "grant_type": "client_credentials",
        "client_id": ak,
        "client_secret": sk,
    }, timeout=30)
    r.raise_for_status()
    data = r.json()
    if "access_token" not in data:
        raise RuntimeError(f"获取 access_token 失败：{data}")
    return data["access_token"]


def recognize_table(token: str, img_path: Path) -> dict:
    b64 = base64.b64encode(img_path.read_bytes()).decode()
    r = httpx.post(
        TABLE_URL,
        params={"access_token": token},
        data={"image": b64},
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        timeout=120,
    )
    r.raise_for_status()
    return r.json()


def cells_to_rows(result: dict) -> list[list[str]]:
    """把百度返回的表格单元格按 row/col 坐标重建成二维表。

    百度「表格文字识别」结构：tables_result[0].body = 单元格列表，
    每个单元格含 row_start/row_end/col_start/col_end（左闭右开，切片语义）+ words；
    header/footer 是表上方/下方的标题文字（无坐标），不参与表格重建。
    """
    tables = result.get("tables_result") or []
    if not tables:
        return []
    cells = tables[0].get("body") or []
    if not cells:
        return []
    n_rows = max(c.get("row_end", 0) for c in cells)
    n_cols = max(c.get("col_end", 0) for c in cells)
    grid = [["" for _ in range(n_cols)] for _ in range(n_rows)]
    for c in cells:
        words = c.get("words", "")
        for r in range(c.get("row_start", 0), c.get("row_end", 0)):
            for col in range(c.get("col_start", 0), c.get("col_end", 0)):
                if not grid[r][col]:
                    grid[r][col] = words
    return grid


def grid_to_text(grid: list[list[str]]) -> str:
    def clean(s: str) -> str:
        # 单元格内可能含换行（表头/长文本折行），压成单行，避免破坏 TSV 结构
        return s.replace("\n", "").replace("\t", " ")
    return "\n".join("\t".join(clean(cell) for cell in row) for row in grid)


def render_page(pdf_path: Path, page_idx: int, scale: float, tmp: Path) -> Path:
    import fitz

    doc = fitz.open(str(pdf_path))
    pix = doc[page_idx].get_pixmap(matrix=fitz.Matrix(scale, scale))
    doc.close()
    img = tmp / f"p{page_idx}.png"
    pix.save(str(img))
    return img


def test_one(token: str, pdf_path: Path, scale: float) -> None:
    print(f"测试文件：{pdf_path.name}")
    with tempfile.TemporaryDirectory() as tmp:
        tmpd = Path(tmp)
        for page_idx in range(5, 20):
            img = render_page(pdf_path, page_idx, scale, tmpd)
            result = recognize_table(token, img)
            if result.get("tables_result"):
                grid = cells_to_rows(result)
                print(f"第 {page_idx + 1} 页识别到表格，{len(grid)} 行，前 30 行：")
                print(grid_to_text(grid[:30]))
                return
            if "error_code" in result:
                print(f"接口报错：{result}")
                return
    print("前 20 页没识别到表格。")


def parse_pages(s: str | None):
    if not s:
        return None
    a, _, b = s.partition("-")
    return (int(a) - 1, int(b) - 1 if b else int(a) - 1)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--src", default=str(DEFAULT_SRC))
    ap.add_argument("--out", default=str(DEFAULT_OUT))
    ap.add_argument("--pages", default=None, help="页范围 1-20")
    ap.add_argument("--scale", type=float, default=2.0)
    ap.add_argument("--test-one", action="store_true")
    ap.add_argument("--reparse", action="store_true", help="从已有 JSON 重建 txt（不调接口、不需 key）")
    args = ap.parse_args()

    if args.reparse:
        out_dir = Path(args.out)
        jsons = sorted(out_dir.glob("*.json"))
        if not jsons:
            sys.exit(f"{out_dir} 下没有 JSON 文件")
        for j in jsons:
            try:
                result = json.loads(j.read_text(encoding="utf-8"))
            except Exception as e:
                print(f"跳过 {j.name}（解析失败 {e}）")
                continue
            grid = cells_to_rows(result)
            if grid:
                j.with_suffix(".txt").write_text(grid_to_text(grid), encoding="utf-8")
                print(f"{len(grid)} 行 -> {j.with_suffix('.txt').name}")
        print(f"重建完成，共处理 {len(jsons)} 个 JSON")
        return

    ak = os.environ.get("BAIDU_OCR_AK", "").strip()
    sk = os.environ.get("BAIDU_OCR_SK", "").strip()
    if not ak or not sk:
        sys.exit("请先设 BAIDU_OCR_AK / BAIDU_OCR_SK 环境变量")

    print("获取 access_token ...")
    token = get_access_token(ak, sk)

    src = Path(args.src)
    if args.test_one:
        test_one(token, src, args.scale)
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
            result = recognize_table(token, img)
            if result.get("tables_result"):
                grid = cells_to_rows(result)
                out = out_dir / f"{src.stem}_p{i + 1}.txt"
                out.write_text(grid_to_text(grid), encoding="utf-8")
                # 原始 JSON 也存一份，便于后续调解析
                (out_dir / f"{src.stem}_p{i + 1}.json").write_text(
                    json.dumps(result, ensure_ascii=False), encoding="utf-8"
                )
                print(f"[{i + 1}/{n}] {len(grid)} 行表格 -> {out.name}")
            else:
                print(f"[{i + 1}/{n}] 无表格" + (f"（报错 {result.get('error_code')}）" if 'error_code' in result else ""))
    doc.close()
    print(f"完成，输出到 {out_dir}")


if __name__ == "__main__":
    main()
