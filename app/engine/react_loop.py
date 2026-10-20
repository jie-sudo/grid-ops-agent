"""ReAct 主控循环（FR-002）：自研状态机，步数上限、死循环检测、二次确认挂起-恢复、反问澄清。"""
from __future__ import annotations

import json
import re
import time
import uuid

from app.config import get_settings
from app.engine.budget import BudgetExceeded, BudgetLedger
from app.engine.checkpoint import CheckpointStore, session_lock
from app.engine.evidence import EvidenceLedger, content_hash, verify_report
from app.engine.guards import Guards
from app.engine.intent_router import IntentRouter
from app.engine.llm import LLMClient, LLMError
from app.engine.memory import Memory
from app.engine.tool_dispatcher import ToolDispatcher
from app.engine.tracer import Tracer

DEVICE_ID_RE = re.compile(r"DEV\d+")
# 这些意图通常明确针对具体设备，缺设备编号时反问（异常处置内的定级/告警可能不针对具体设备，交给 LLM clarify）
NEEDS_DEVICE_INTENTS = {"状态查询"}

SYSTEM_PROMPT = """你是电网智能运维助手。诊断、缺陷分级、告警判定、量测查询必须调用工具，不得自己编造数值。

可用工具：
{tools}

严格只输出一个 JSON 对象，格式三选一：
- 调用工具：{{"action":"tool_call","tool":"工具名","params":{{...}}}}
- 最终结论：{{"action":"final_answer","answer":"结论","sources":["来源"]}}
- 信息不足需澄清：{{"action":"clarify","question":"要澄清的问题"}}

规则：
1. 知识问答先调用 retrieve_knowledge，答案附出处；检索不到就答"未检索到依据"。
2. 结论必须附来源（工具返回数据或知识片段出处）。
3. 数值必须来自工具返回，不得自己编造；信息不足、不确定就输出 clarify。
4. 一次只输出一个 JSON 对象，不要输出解释文字。
5. 诊断/告警分析时，可调用 search_review_cases 查历史处置案例作参考；未命中不影响继续排查。
"""

# 按意图注入的定向提示（软先验，不锁工具；AegisOps Action Handler build_prompt_hints 同思路）。
# 目的：减少"先大范围取证再动手"的过度工具调用，降 token 与延迟。
INTENT_HINTS = {
    "工单生成": "用户要出工单。等级判定优先级：① 原文已明说等级（一般/严重/危急）→ 直接调 create_workorder_draft 出草稿；② 症状指向设备量测（温度/电流/局放等）→ 调 query_state 拿该设备四态评价与数值依据，据此定级；③ 定性描述（闪络/爬电/烧毁等）→ 调 grade_defect；④ 仍定不出 → 反问用户等级。不要同时调 query_device/query_measurements/query_alarms 等多个查询工具。",
    "状态查询": "直接调 query_state 或 query_device 查询指定设备，不要反复调用量测/告警。",
    "异常处置": "设备出了异常，先判断用户给的是什么：有告警信号 → 调 query_alarms / alarm_level；有缺陷描述要定级 → 调 grade_defect；要查原因 → 调 diagnose 或 query_state。缺设备编号先反问，不要大范围查量测。",
    "问答": "先调 retrieve_knowledge 检索知识库，答案附出处。",
}


class AgentLoop:
    def __init__(self) -> None:
        self.settings = get_settings()
        self.llm = LLMClient()
        self.dispatcher = ToolDispatcher()
        self.memory = Memory()
        self.tracer = Tracer()
        self.guards = Guards()
        self.router = IntentRouter()
        self.checkpoint = CheckpointStore()

    def run(self, session_id: str, user_message: str, on_event=None) -> dict:
        """对外入口：先按会话加 advisory lock 串行化（best-effort），再执行主循环。"""
        with session_lock(session_id):
            return self._run_impl(session_id, user_message, on_event)

    def _run_impl(self, session_id: str, user_message: str, on_event=None) -> dict:
        def emit(event_type: str, **data):
            if on_event:
                on_event({"type": event_type, **data})

        # 挂起确认恢复（二次确认闸口）：优先 Redis，Redis 丢失时从 PG 检查点恢复
        state = self.memory.get_state(session_id)
        if not state.get("awaiting_confirm"):
            saved = self.checkpoint.load(session_id)
            if saved and saved.get("awaiting_confirm") and saved.get("draft"):
                state = {
                    "awaiting_confirm": True,
                    "draft": saved["draft"],
                    "intent": saved.get("intent"),
                }
                self.memory.set_state(session_id, state)
                if saved.get("anchors"):
                    self.memory.set_anchors(session_id, saved["anchors"])
        if state.get("awaiting_confirm"):
            return self._handle_confirm(session_id, user_message, state)

        self.memory.append_history(session_id, "user", user_message)
        # 从用户文本抽取设备编号，维护多实体锚点（支撑跨多轮指代）
        self._update_anchors(session_id, user_message)
        intent, confidence = self.router.route(user_message)
        emit("intent", intent=intent, confidence=confidence)

        # 反问①：意图低置信
        if confidence < 0.6:
            q = "抱歉，我不太确定您的意图。您是想查询设备、分析异常还是出工单？"
            emit("clarify", question=q)
            return self._clarify(session_id, q)

        # 反问②：关键实体（设备编号）缺失
        if intent in NEEDS_DEVICE_INTENTS and not self._has_device(user_message, session_id):
            q = "请提供设备编号（例如 DEV000001），我才能继续。"
            emit("clarify", question=q)
            return self._clarify(session_id, q)

        # 确定性快路径：工单生成（意图单一、参数明确，不走 LLM 工具选择，稳且快）
        if intent == "工单生成":
            result = self._workorder_fastpath(session_id, user_message, emit)
            if result is not None:
                return result

        anchors = self.memory.get_anchors(session_id)
        device_ctx = ""
        if anchors.get("devices"):
            device_ctx = (
                f"\n\n【会话记忆】本会话已提及的设备：{'、'.join(anchors['devices'])}"
                f"（最近讨论：{anchors.get('device_id')}）。"
                f"用户用「那台/它/第一台/上一台」等指代时，请结合此列表和对话历史判断所指设备。"
            )
        intent_hint = INTENT_HINTS.get(intent, "")
        intent_ctx = f"\n\n【当前意图】{intent}。{intent_hint}" if intent_hint else ""
        messages = [
            {
                "role": "system",
                "content": SYSTEM_PROMPT.format(
                    tools=json.dumps(self.dispatcher.list_schemas(), ensure_ascii=False, indent=2)
                ) + device_ctx + intent_ctx,
            }
        ]
        for h in self.memory.get_history(session_id):
            messages.append({"role": h["role"], "content": h["content"]})

        run_id = uuid.uuid4().hex
        ledger = EvidenceLedger(session_id, run_id)
        budget = BudgetLedger(run_id, session_id=session_id)

        tool_results: list[dict] = []
        last_call = None
        for step in range(1, self.settings.max_steps + 1):
            try:
                budget.reserve(messages)
            except BudgetExceeded as e:
                return self._finish(session_id, f"预算耗尽：{e}", [])
            action = self._llm_action(messages)
            budget.reconcile(getattr(self.llm, "last_usage", None))
            if action is None:
                return self._finish(session_id, "无法理解，请细化问题", [])

            if action.get("action") == "clarify":
                q = action.get("question", "请补充信息")
                emit("clarify", question=q)
                return self._clarify(session_id, q)

            if action.get("action") == "final_answer":
                answer = action.get("answer", "")
                sources = action.get("sources", [])
                ok, issues = verify_report(answer, sources, ledger, user_message)
                if issues:
                    answer = f"{answer}\n\n（溯源提示：{'；'.join(issues)}）"
                emit("final_answer", answer=answer, sources=sources)
                result = self._finish(session_id, answer, sources)
                result["verification"] = {"passed": ok, "issues": issues}
                result["budget"] = budget.summary()
                return result

            if action.get("action") == "tool_call":
                tool = action.get("tool", "")
                params = action.get("params", {})
                # 定级工具：从会话锚点注入设备类型（确定性，不进 prompt，不依赖 LLM 判断）
                if tool == "grade_defect" and not params.get("device_type"):
                    dt = self._current_device_type(session_id)
                    if dt:
                        params = {**params, "device_type": dt}
                key = (tool, json.dumps(params, sort_keys=True, default=str))
                if last_call == key:  # 死循环检测
                    return self._finish(session_id, "检测到重复无效调用，请细化问题", [])
                last_call = key

                emit("tool_call", tool=tool, params=params)
                t0 = time.time()
                result = self.dispatcher.execute(tool, params)
                elapsed = int((time.time() - t0) * 1000)
                emit("tool_result", tool=tool, result=result)

                # 实体锚点：记录设备编号，维护设备栈（支撑多轮指代）
                device_id = params.get("device_id") or (result.get("device") or {}).get("device_id")
                if device_id:
                    self._update_anchors(session_id, device_id)

                # 二次确认：工单草稿挂起
                if self.guards.is_confirm_needed(result):
                    self.memory.set_state(session_id, {
                        "awaiting_confirm": True,
                        "draft": result["draft"],
                        "intent": intent,
                    })
                    self.checkpoint.save(
                        session_id, run_id,
                        step=step, intent=intent,
                        awaiting_confirm=True, draft=result["draft"],
                        anchors=self.memory.get_anchors(session_id),
                    )
                    emit("confirm_required", preview=result["draft"], message=result.get("message", "请确认是否落库"))
                    return {
                        "type": "confirm_required",
                        "preview": result["draft"],
                        "message": result.get("message", "请确认是否落库"),
                    }

                if self.guards.is_degraded(result):
                    emit("degraded", tool=tool, reason=result.get("reason"))

                tool_results.append({"params": params, "result": result})
                ledger.add(tool, params, result)
                self.tracer.record(
                    session_id, step, tool, params, result,
                    elapsed_ms=elapsed,
                    degraded=self.guards.is_degraded(result),
                )
                messages.append({"role": "assistant", "content": json.dumps(action, ensure_ascii=False)})
                messages.append({"role": "user", "content": json.dumps({"observation": result}, ensure_ascii=False, default=str)})
                continue

            # 非法协议 → 自纠一次
            messages.append({"role": "user", "content": "输出格式非法，请只输出 JSON（action 为 tool_call / final_answer / clarify）"})

        return self._finish(session_id, "已达最大步数，请细化问题", [])

    def _workorder_fastpath(self, session_id: str, user_message: str, emit) -> dict:
        """工单生成意图的确定性快路径：不走 LLM 工具选择，稳、快、安全。

        定级优先级：① 原文显式等级 ② query_state 设备状态 → 映射缺陷等级
        ③ grade_defect 关键词 ④ 仍定不出 → 反问。草稿仍走二次确认闸口（人工确认才落库）。
        """
        from app.engine.rule_engine import get_engine
        from app.skills import query as query_skill
        from app.skills import workorder as wo_skill

        device_id = None
        m = DEVICE_ID_RE.search(user_message)
        if m:
            device_id = m.group(0)

        # ① 原文显式等级
        level = next((lv for lv in ("危急", "严重", "一般") if lv in user_message), None)

        # 内容：优先取冒号后的描述；否则整句去掉引导词
        if "：" in user_message or ":" in user_message:
            content = re.split(r"[：:]", user_message)[-1].strip()
        else:
            content = user_message
            for w in ("帮我", "给我", "请", "出个", "出一个", "生成一个", "生成", "创建", "工单", "派单", "缺陷"):
                content = content.replace(w, "")
            content = content.replace(device_id or "", "").strip("：:，,。.；; 的给为是").strip()
        if not content:
            content = "缺陷工单"

        # ② 设备状态 → 缺陷等级
        if level is None and device_id:
            st = query_skill.query_state(device_id)
            if st.get("found"):
                mapped = get_engine().map_state_to_defect(st.get("state"))
                if mapped:
                    level = mapped
                else:
                    basis = "；".join(st.get("basis") or [])
                    answer = f"设备 {device_id} 当前状态为「{st.get('state')}」"
                    if basis:
                        answer += f"（{basis}）"
                    answer += f"，未见越限缺陷，无法按「{content}」生成工单。如确有缺陷，请补充具体数值或明确等级（一般/严重/危急）。"
                    emit("final_answer", answer=answer, sources=[])
                    return self._finish(session_id, answer, [])

        # ③ 关键词定级
        if level is None:
            g = get_engine().grade_defect(content)
            if not g.get("degraded") and g.get("level"):
                level = g["level"]

        # ④ 仍定不出 → 反问
        if level is None:
            q = "无法确定缺陷等级（避免误判，绝不默认）。请补充具体数值（当前值/限值/越限幅度）或直接说明等级（一般/严重/危急）。"
            emit("clarify", question=q)
            return self._clarify(session_id, q)

        draft = wo_skill.create_workorder_draft(level, content, device_id)
        self.memory.set_state(session_id, {"awaiting_confirm": True, "draft": draft["draft"], "intent": "工单生成"})
        self.checkpoint.save(
            session_id, uuid.uuid4().hex, step=0, intent="工单生成",
            awaiting_confirm=True, draft=draft["draft"],
            anchors=self.memory.get_anchors(session_id),
        )
        emit("confirm_required", preview=draft["draft"], message=draft.get("message", "请确认是否落库"))
        return {"type": "confirm_required", "preview": draft["draft"], "message": draft.get("message", "请确认是否落库")}

    def _llm_action(self, messages: list[dict]) -> dict | None:
        try:
            return self.llm.chat_json(messages)
        except LLMError:
            return None

    def _update_anchors(self, session_id: str, text: str) -> None:
        """从用户文本抽取设备编号，维护多实体锚点（设备栈 + 焦点设备）。"""
        ids = DEVICE_ID_RE.findall(text)
        if not ids:
            return
        anchors = self.memory.get_anchors(session_id)
        devices = anchors.get("devices", [])
        for did in ids:
            if did in devices:
                devices.remove(did)
            devices.insert(0, did)
        anchors["devices"] = devices[:5]  # 保留最近 5 个
        anchors["device_id"] = ids[0]
        self.memory.set_anchors(session_id, anchors)

    def _has_device(self, text: str, session_id: str) -> bool:
        if DEVICE_ID_RE.search(text):
            return True
        return bool(self.memory.get_anchors(session_id).get("device_id"))

    def _current_device_type(self, session_id: str) -> str | None:
        """从会话锚点查最近设备的类型（确定性，用于缺陷库按设备筛选）。"""
        device_id = self.memory.get_anchors(session_id).get("device_id")
        if not device_id:
            return None
        try:
            from app.data import repository

            device = repository.get_device(device_id)
            return device.get("device_type") if device else None
        except Exception:
            return None

    def _clarify(self, session_id: str, question: str) -> dict:
        self.memory.append_history(session_id, "assistant", question)
        return {"type": "clarify", "question": question}

    def _handle_confirm(self, session_id: str, user_message: str, state: dict) -> dict:
        # 用 LLM 判断确认/取消（替代脆弱的关键词匹配）
        try:
            out = self.llm.chat_json([
                {
                    "role": "system",
                    "content": '判断用户对工单草稿的回复意图。确认落库输出 {"confirm": true}，'
                               '取消或拒绝输出 {"confirm": false}。',
                },
                {"role": "user", "content": user_message},
            ])
            confirmed = bool(out.get("confirm", False))
        except LLMError:
            return self._clarify(session_id, "请明确回复「确认」或「取消」")

        if confirmed:
            draft = state.get("draft") or {}
            idem_key = content_hash({"session_id": session_id, "draft": draft})
            result = self.dispatcher.execute(
                "create_work_order", {"order": draft, "idempotency_key": idem_key}
            )
            self.memory.clear_state(session_id)
            self.checkpoint.clear(session_id)
            if "error" in result:
                return self._finish(session_id, f"落库失败：{result['error']}", [])
            if not result.get("duplicate"):
                self._draft_review_case(session_id, draft)
            answer = f"工单已落库：{result.get('order_id')}"
            if result.get("duplicate"):
                answer = f"工单此前已落库（幂等）：{result.get('order_id')}"
            self.memory.append_history(session_id, "assistant", answer)
            return {"type": "final_answer", "answer": answer, "sources": []}

        self.memory.clear_state(session_id)
        self.checkpoint.clear(session_id)
        self.memory.append_history(session_id, "assistant", "已取消，未落库")
        return {"type": "final_answer", "answer": "已取消，未落库", "sources": []}

    def _draft_review_case(self, session_id: str, draft: dict) -> None:
        """从已确认工单沉淀一条复盘案例草稿（best-effort，失败不影响确认响应）。"""
        try:
            from app.data import repository
            from app.skills import review_case

            device_type = "通用"
            if draft.get("ref_id"):
                device = repository.get_device(draft["ref_id"])
                if device:
                    device_type = device.get("device_type", "通用")
            diagnosis = repository.latest_diagnosis(session_id)
            case = review_case.draft_from_workorder(
                draft, device_type=device_type, diagnosis=diagnosis, session_id=session_id
            )
            repository.create_review_case(case)
        except Exception:
            pass

    def _finish(self, session_id: str, answer: str, sources: list) -> dict:
        self.memory.append_history(session_id, "assistant", answer)
        return {"type": "final_answer", "answer": answer, "sources": sources}
