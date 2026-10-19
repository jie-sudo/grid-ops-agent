"""OCR 清洗纯函数单测。"""
from app.data.ocr_clean import (
    clean_ocr_text,
    is_ad_page,
    is_cover_toc_page,
    is_page_number,
    split_pages,
)


def test_split_pages():
    text = "===== 第 1 页 =====\nA\n===== 第 2 页 =====\nB\n"
    assert split_pages(text) == [(1, "A"), (2, "B")]


def test_is_ad_page():
    assert is_ad_page("电力工程资料\n长按二维码加入星球下载\n已有9999+人加入学习")
    assert not is_ad_page("4.1 架空线路缺陷类别")


def test_is_cover_toc_page():
    assert is_cover_toc_page("ICS 27.100\n备案号：36423-2012\n国家能源局 发布")
    assert is_cover_toc_page("目次\n1 范围……\n2 规范性引用文件……")
    assert not is_cover_toc_page("4.1.1 杆塔本体")


def test_is_page_number():
    assert is_page_number("1")
    assert is_page_number("II")
    assert not is_page_number("1）水泥杆本体倾斜度")


def test_clean_drops_ad_header_page_number():
    raw = (
        "===== 第 1 页 =====\nQ / GDW 745 — 2012\n4.1 架空线路缺陷类别\n"
        "===== 第 2 页 =====\n电力工程资料\n长按二维码加入星球下载\n"
        "===== 第 3 页 =====\nQ / GDW 745 — 2012\n4.1.1 杆塔\n"
        "===== 第 4 页 =====\nQ / GDW 745 — 2012\n4.1.1.1 杆塔本体\n1）水泥杆本体倾斜度≥3%\n2\n"
    )
    clean = clean_ocr_text(raw)
    assert "星球" not in clean          # 广告页丢弃
    assert "Q / GDW 745 — 2012" not in clean  # 页眉去重
    assert "4.1.1.1 杆塔本体" in clean
    assert "水泥杆本体倾斜度" in clean
    assert "\n2" not in clean + "\n"    # 页码丢弃（末尾的 "2"）


def test_clean_drops_garbled_line():
    raw = "===== 第 1 页 =====\n4.1 杆塔\nÉx-28a zeme E4cterm% a ser\n水泥杆倾斜度≥3%\n"
    clean = clean_ocr_text(raw)
    assert "杆塔" in clean
    assert "Éx-28a" not in clean
    assert "水泥杆倾斜度" in clean


def test_watermark_line_not_page_dropped():
    # "电力图书馆知识星球" 是每页水印，只丢这一行，不能整页丢（否则正文被清空）
    raw = (
        "===== 第 1 页 =====\n电力图书馆知识星球\n4.1 架空线路缺陷类别\n"
        "===== 第 2 页 =====\n电力图书馆知识星球\n4.1.1 杆塔\n"
    )
    clean = clean_ocr_text(raw)
    assert "电力图书馆" not in clean
    assert "架空线路缺陷类别" in clean
    assert "杆塔" in clean


def test_repeated_chinese_level_marker_not_dropped():
    # "a）危急缺陷" 在每个章节都出现，是有中文的正文标记，不能当页眉删掉
    raw = (
        "===== 第 1 页 =====\nQ / GDW 745 — 2012\n4.1.1.1 杆塔本体\na）危急缺陷\n1）倾斜度≥3%\n"
        "===== 第 2 页 =====\nQ / GDW 745 — 2012\n4.1.1.2 基础\na）危急缺陷\n1）埋深不足\n"
        "===== 第 3 页 =====\nQ / GDW 745 — 2012\n4.1.2 导线\na）危急缺陷\n1）断股\n"
    )
    clean = clean_ocr_text(raw)
    assert "a）危急缺陷" in clean  # 等级标记保留
    assert "Q / GDW 745 — 2012" not in clean  # 无中文的页眉被删
