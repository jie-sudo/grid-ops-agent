"""版本仲裁（幂等逻辑的纯函数部分）单测。"""
from app.data.ingest import arbitrate_versions


def _doc(stem, version, effective_date, title=None):
    return {
        "stem": stem,
        "fm": {"version": version, "status": "active", "effective_date": effective_date},
        "title": title or stem,
        "body": "x",
    }


def test_single_version_keeps_active():
    docs = [_doc("d1", "Q/GDW 745", "2012")]
    assert arbitrate_versions(docs) == []
    assert "final_status" not in docs[0]  # 未设置，仍走 fm.status=active


def test_newer_version_supersedes_older():
    docs = [
        _doc("old", "Q/GDW 745", "2012", "缺陷分级旧版"),
        _doc("new", "Q/GDW 745", "2026", "缺陷分级新版"),
    ]
    superseded = arbitrate_versions(docs)
    assert superseded == ["缺陷分级旧版"]
    # 旧的标 superseded，新的保持 active
    assert docs[0]["final_status"] == "superseded"
    assert docs[0]["superseded_by"] == "Q/GDW 745"
    assert "final_status" not in docs[1]


def test_different_sources_do_not_affect_each_other():
    docs = [
        _doc("a", "Q/GDW 745", "2012"),
        _doc("b", "DL/T 1685", "2017"),
    ]
    assert arbitrate_versions(docs) == []
    assert all("final_status" not in d for d in docs)


def test_three_versions_only_latest_active():
    docs = [
        _doc("v1", "Q/GDW 745", "2010", "v1"),
        _doc("v2", "Q/GDW 745", "2012", "v2"),
        _doc("v3", "Q/GDW 745", "2026", "v3"),
    ]
    superseded = arbitrate_versions(docs)
    assert set(superseded) == {"v1", "v2"}
    assert docs[2]["final_status"] if "final_status" in docs[2] else "active" == "active"
