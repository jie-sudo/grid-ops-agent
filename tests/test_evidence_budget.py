"""证据溯源 + 预算账本（纯逻辑，不需 LLM / DB / Redis）。

evidence.py 与 budget.py 的校验/记账算术不依赖外部服务，进程内即可测；
持久化走 best-effort（表未建时静默跳过）。
"""
from app.engine.budget import BudgetExceeded, BudgetState
from app.engine.evidence import EvidenceLedger, content_hash, verify_report


def test_content_hash_stable_and_order_independent():
    assert content_hash({"a": 1, "b": 2}) == content_hash({"b": 2, "a": 1})
    assert content_hash({"a": 1}) != content_hash({"a": 2})


def test_workorder_idempotency_key_deterministic():
    # 与 react_loop._handle_confirm 相同的派生方式：同草稿 → 同幂等键，草稿变 → 键变
    draft = {"ref_type": "缺陷", "content": "换油", "level": "严重", "device_id": "DEV1"}
    k1 = content_hash({"session_id": "s", "draft": draft})
    k2 = content_hash({"session_id": "s", "draft": dict(draft)})
    assert k1 == k2
    changed = dict(draft, level="危急")
    assert k1 != content_hash({"session_id": "s", "draft": changed})


def test_verify_report_number_traceable_from_evidence():
    ledger = EvidenceLedger("s1")
    ledger.add("query_state", {"device_id": "DEV1"}, {"state": "严重", "basis": ["温度=95℃"]})
    ok, issues = verify_report("设备温度 95 度，状态严重", [], ledger, "DEV1")
    assert not any("数值无法溯源" in i for i in issues)


def test_verify_report_fabricated_number_flagged():
    ledger = EvidenceLedger("s2")
    ledger.add("query_state", {"device_id": "DEV1"}, {"state": "正常"})
    ok, issues = verify_report("温度是 128 度", [], ledger, "DEV1")
    assert not ok
    assert any("128" in i for i in issues)


def test_verify_report_missing_sources_flagged():
    ledger = EvidenceLedger("s3")
    ledger.add("retrieve_knowledge", {"question": "q"}, {"chunks": [{"title": "规程A", "content": "..."}]})
    ok, issues = verify_report("依据规程A应处理", [], ledger, "q")
    assert any("缺少来源" in i for i in issues)


def test_verify_report_untraceable_source_flagged():
    ledger = EvidenceLedger("s4")
    ledger.add("retrieve_knowledge", {"question": "q"}, {"chunks": [{"title": "规程A", "content": "..."}]})
    ok, issues = verify_report("结论", ["规程Z"], ledger, "q")
    assert any("无法溯源" in i for i in issues)


def test_verify_report_traceable_source_ok():
    ledger = EvidenceLedger("s5")
    ledger.add("retrieve_knowledge", {"question": "q"}, {"chunks": [{"title": "规程A", "content": "..."}]})
    ok, issues = verify_report("结论", ["规程A"], ledger, "q")
    assert ok


def test_verify_report_source_naming_used_tool_ok():
    # LLM 给的来源是自然语言描述、点名了实际调用的工具 → 不应误报
    ledger = EvidenceLedger("s6")
    ledger.add("query_state", {"device_id": "DEV000001"}, {"state": "正常", "basis": ["温度=58.5℃，上限=85℃"]})
    ok, issues = verify_report(
        "设备状态正常", ["query_state(DEV000001) 状态四态评价返回"], ledger, "设备 DEV000001"
    )
    assert not any("来源无法溯源" in i for i in issues)


def test_verify_report_fabricated_source_flagged():
    # 来源点名了一个没被调用的工具 → 应标记
    ledger = EvidenceLedger("s7")
    ledger.add("query_state", {"device_id": "DEV1"}, {"state": "正常"})
    ok, issues = verify_report("结论", ["query_device(DEV9) 返回"], ledger, "")
    assert any("来源无法溯源" in i for i in issues)


def test_budget_reserve_then_reconcile():
    st = BudgetState(max_requests=3, max_tokens=1000)
    st.reserve(100)
    st.reconcile(100, 60, None)  # 实际 60 → 退回 40
    assert st.charged_tokens == 60
    st.reserve(100)
    assert st.requests == 2


def test_budget_unknown_usage_keeps_reservation():
    st = BudgetState(max_requests=3, max_tokens=1000)
    st.reserve(100)
    st.reconcile(100, None, None)  # 供应商未返回 usage → 保留预留，不当作零
    assert st.charged_tokens == 100


def test_budget_request_exceeded():
    st = BudgetState(max_requests=1, max_tokens=1000)
    st.reserve(100)
    try:
        st.reserve(100)
        assert False, "应抛出 BudgetExceeded"
    except BudgetExceeded:
        pass


def test_budget_token_exceeded():
    st = BudgetState(max_requests=10, max_tokens=500)
    try:
        st.reserve(600)
        assert False, "应抛出 BudgetExceeded"
    except BudgetExceeded:
        pass
