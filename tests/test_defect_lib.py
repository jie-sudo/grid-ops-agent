"""结构化缺陷库抽取 + 匹配单测。"""
from app.data.defect_lib import match_defect_library, parse_defect_library


def test_parse_defect_library():
    text = (
        "4 配电网设备缺陷分类\n"
        "4.1 架空线路缺陷类别\n"
        "4.1.1 杆塔\n"
        "4.1.1.1 杆塔本体\n"
        "a）危急缺陷\n"
        "1）水泥杆本体倾斜度≥3%\n"
        "2）水泥杆杆身有纵向裂纹\n"
        "b）严重缺陷\n"
        "1）水泥杆本体倾斜度2%~3%\n"
        "4.1.2 导线\n"
        "a）危急缺陷\n"
        "1）导线断股\n"
    )
    records = parse_defect_library(text)
    assert len(records) == 4
    assert records[0] == {
        "device_category": "4.1 架空线路缺陷类别",
        "component": "4.1.1 杆塔",
        "part": "4.1.1.1 杆塔本体",
        "level": "危急",
        "defect": "水泥杆本体倾斜度≥3%",
    }
    assert records[1]["level"] == "危急"
    assert records[2]["level"] == "严重"
    # 导线是部件（depth 2）、无部位子级，part 为空、comp 记录它
    assert records[3]["component"] == "4.1.2 导线"
    assert records[3]["part"] == ""
    assert records[3]["defect"] == "导线断股"


def test_parse_defect_library_multiline_item():
    # 条目被 OCR 断行，应累积到同一条
    text = (
        "4.1 架空线路缺陷类别\n"
        "4.1.1 杆塔\n"
        "4.1.1.1 杆塔本体\n"
        "a）危急缺陷\n"
        "1）水泥杆本体倾斜度≥3%，50m以下高度铁塔塔身倾斜度≥2%、50m及以上\n"
        "高度铁塔塔身倾斜度≥1.5%\n"
    )
    records = parse_defect_library(text)
    assert len(records) == 1
    assert "高度铁塔塔身倾斜度≥1.5%" in records[0]["defect"]


def test_match_defect_library_unambiguous():
    records = [
        {"component": "4.1.1 杆塔", "part": "4.1.1.1 杆塔本体", "level": "危急", "defect": "水泥杆杆身有纵向裂纹，横向裂纹宽度超过0.5mm"},
        {"component": "4.1.1 杆塔", "part": "4.1.1.1 杆塔本体", "level": "严重", "defect": "水泥杆杆身横向裂纹宽度在0.4~0.5mm之间"},
    ]
    level, rec = match_defect_library("水泥杆杆身有纵向裂纹", records)
    assert level == "危急"


def test_match_defect_library_device_filter():
    records = [
        {"device_type": "柱上真空开关", "level": "严重", "defect": "无法储能"},
        {"device_type": "SF6断路器", "level": "危急", "defect": "无法储能"},
    ]
    # 不指定设备 → 两个都命中 → 歧义 → 不定级
    assert match_defect_library("无法储能", records)[0] is None
    # 指定"断路器" → 只匹配 SF6断路器 → 危急
    assert match_defect_library("无法储能", records, device_type="断路器")[0] == "危急"
    # 指定"柱上" → 只匹配柱上真空开关 → 严重
    assert match_defect_library("无法储能", records, device_type="柱上")[0] == "严重"


def test_match_defect_library_ambiguous_returns_none():
    records = [
        {"level": "危急", "defect": "水泥杆本体倾斜度≥3%"},
        {"level": "严重", "defect": "水泥杆本体倾斜度2%~3%"},
        {"level": "一般", "defect": "水泥杆本体倾斜度1.5%~2%"},
    ]
    level, rec = match_defect_library("水泥杆倾斜度2.5%", records)
    assert level is None  # 多等级歧义 → 不定级（安全）


def test_grade_defect_defect_library_fallback():
    from app.engine.rule_engine import RuleEngine

    e = RuleEngine()
    r = e.grade_defect("水泥杆杆身有纵向裂纹")  # 不在关键词里，但缺陷库能匹配到危急
    assert r["level"] == "危急"
    assert r["degraded"] is False
    # 真正的歧义仍降级
    r2 = e.grade_defect("水泥杆倾斜度2.5%")
    assert r2["degraded"] is True
