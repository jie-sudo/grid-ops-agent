"""结构感知切分纯函数单测。"""
from app.data.kb import chunk_structured


def test_chunk_structured_keeps_section_with_levels():
    text = (
        "4.1.1.1 杆塔本体\n"
        "a）危急缺陷\n"
        "1）水泥杆本体倾斜度≥3%\n"
        "2）水泥杆杆身有纵向裂纹\n"
        "b）严重缺陷\n"
        "1）水泥杆本体倾斜度2%~3%\n"
        "2）杆塔镀锌层脱落\n"
    )
    chunks = chunk_structured(text, size=700)
    # 一个章节内危急/严重阈值放在一起，供定级比较
    assert len(chunks) == 1
    assert chunks[0].startswith("4.1.1.1 杆塔本体\na）危急缺陷")
    assert "水泥杆本体倾斜度≥3%" in chunks[0]
    assert "严重缺陷" in chunks[0]


def test_chunk_structured_continuation_carries_section_title():
    # 一个章节内容超长时，延续块也带章节标题做上下文
    lines = ["4.1.1.1 杆塔本体"] + [f"1）缺陷条目{i}描述内容" for i in range(100)]
    text = "\n".join(lines)
    chunks = chunk_structured(text, size=200)
    assert len(chunks) > 1
    # 每个块都以章节标题开头
    for c in chunks:
        assert c.startswith("4.1.1.1 杆塔本体")


def test_chunk_structured_no_structure_falls_back():
    # 无章节/等级标记的文本退化为按长度切
    text = "\n".join(f"第{i}句普通内容" for i in range(200))
    chunks = chunk_structured(text, size=200)
    assert len(chunks) > 1
    assert "".join(chunks).replace("\n", "") == text.replace("\n", "")


def test_chunk_metrics():
    from app.data.kb import chunk_metrics
    chunks = [
        "4.1.1.1 杆塔本体\na）危急缺陷\n1）倾斜度≥3%",
        "4.1.1.2 基础\na）危急缺陷\n1）埋深不足",
    ]
    m = chunk_metrics(chunks)
    assert m["chunks"] == 2
    assert m["orphan"] == 0
    assert m["over_embed"] == 0
    assert m["with_header_ratio"] == 1.0
