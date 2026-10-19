"""证据账本与溯源校验（借鉴 AegisOps `verify_report`，适配电网域）。

把每次工具返回的"事实"登记为带内容哈希的证据记录，最终回答里的
来源与数值必须能追溯到「用户输入 ∪ 工具参数 ∪ 工具返回」，否则标注
"请人工核实"。确定性判定在规则引擎，这里只做可追溯性校验，不做语义判断。

持久化为 best-effort（表未建 / 库不可用时不阻断主流程），核心校验在
进程内即可完成，保证"单次运行内"防幻觉成立。
"""
from __future__ import annotations

import hashlib
import json
import re
import uuid
from datetime import datetime, timezone


def canonical_json(value) -> str:
    """规范化 JSON：键排序 + 紧凑分隔符，使同一对象哈希稳定（与键顺序无关）。"""
    return json.dumps(value, ensure_ascii=False, sort_keys=True, default=str, separators=(",", ":"))


def content_hash(value) -> str:
    """内容 SHA256 哈希：证据完整性的锚点。"""
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


_NUMBER_RE = re.compile(r"\b\d+(?:\.\d+)?\b")


def _numbers(text: str) -> set[str]:
    return set(_NUMBER_RE.findall(text or ""))


class EvidenceLedger:
    """单次运行内的事实账本：登记工具返回，供最终回答溯源。"""

    def __init__(self, session_id: str, run_id: str | None = None) -> None:
        self.session_id = session_id
        self.run_id = run_id or uuid.uuid4().hex
        self._records: list[dict] = []

    def add(self, tool: str, params: dict | None, result: dict) -> dict:
        """登记一次工具返回，返回证据记录（含稳定 evidence_id 与内容哈希）。"""
        params = params or {}
        rec = {
            "evidence_id": f"E{uuid.uuid5(uuid.NAMESPACE_URL, f'{self.run_id}:{tool}:{content_hash(result)}').hex[:24]}",
            "tool": tool,
            "params": params,
            "params_hash": content_hash(params),
            "result": result,
            "content_hash": content_hash(result),
            "created_at": datetime.now(timezone.utc).isoformat(),
            "degraded": bool(result.get("degraded")) if isinstance(result, dict) else False,
        }
        self._records.append(rec)
        self._persist(rec)
        return rec

    def _persist(self, rec: dict) -> None:
        """审计持久化（best-effort：新表未建 / 库不可用时不阻断主流程）。"""
        try:
            from app.data import models
            from app.data.database import get_write_session

            with get_write_session() as s:
                s.add(models.EvidenceRecord(
                    evidence_id=rec["evidence_id"],
                    session_id=self.session_id,
                    tool=rec["tool"],
                    params_hash=rec["params_hash"],
                    content_hash=rec["content_hash"],
                    result=canonical_json(rec["result"])[:4096],
                    degraded=rec["degraded"],
                ))
                s.commit()
        except Exception:
            pass

    def records(self) -> list[dict]:
        return list(self._records)

    def used_knowledge(self) -> bool:
        """是否用过知识/诊断/状态工具（这些工具要求结论附来源）。"""
        return any(r["tool"] in ("retrieve_knowledge", "diagnose", "query_state") for r in self._records)

    def tools_used(self) -> set[str]:
        """本次运行实际调用的工具名集合（来源解析用）。"""
        return {r["tool"] for r in self._records}

    def knowledge_sources(self) -> set[str]:
        """知识检索返回的出处（title/source），用于来源解析。"""
        out: set[str] = set()
        for r in self._records:
            if r["tool"] != "retrieve_knowledge":
                continue
            for c in (r["result"].get("chunks") or []):
                for key in ("title", "source"):
                    v = c.get(key)
                    if v:
                        out.add(str(v))
        return out

    def all_text(self) -> str:
        """「已知数值池」：工具参数 + 工具返回（数值溯源的范围，不含答案本身）。"""
        parts = [canonical_json(r["params"]) for r in self._records]
        parts += [canonical_json(r["result"]) for r in self._records]
        return "\n".join(parts)


def verify_report(
    answer: str,
    sources: list | None,
    ledger: EvidenceLedger,
    user_text: str = "",
) -> tuple[bool, list[str]]:
    """校验最终回答的可追溯性，返回 (是否通过, 问题列表)。不拦截，仅标注。

    检查项：
    1. 用到知识/诊断却无来源 → 提示；
    2. 来源字符串无法追溯到证据账本（知识出处 / 证据 ID / 内容子串）→ 提示；
    3. 答案里 >1 的数值无法追溯到「用户输入 ∪ 工具参数 ∪ 工具返回」→ 提示待核实。
    """
    issues: list[str] = []
    sources = sources or []
    all_text = ledger.all_text()
    known_numbers = _numbers(user_text) | _numbers(all_text)

    if ledger.used_knowledge() and not sources:
        issues.append("结论缺少来源")

    know_sources = ledger.knowledge_sources()
    evidence_ids = {r["evidence_id"] for r in ledger.records()}
    tools_used = ledger.tools_used()
    generic_source_phrases = ("工具返回", "工具结果", "工具调用", "查询结果", "查询返回")
    for src in sources:
        s = str(src)
        if not s:
            continue
        if s in know_sources or s in evidence_ids or s in all_text:
            continue
        if any(tool and tool in s for tool in tools_used):
            continue  # 来源点名了本次实际调用的工具 → 可溯源
        if tools_used and any(p in s for p in generic_source_phrases):
            continue  # 泛化的"工具返回数据"式来源，且确实调过工具 → 可接受
        issues.append(f"来源无法溯源：{s}")

    for n in sorted(_numbers(answer), key=lambda x: -len(x)):
        if float(n) <= 1 or n in known_numbers:
            continue
        issues.append(f"数值无法溯源：{n}")

    return (not issues), issues
