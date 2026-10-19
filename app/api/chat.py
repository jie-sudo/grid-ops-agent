"""对话入口：/api/v1/chat（同步）与 /api/v1/chat/stream（SSE 流式）。"""
from __future__ import annotations

import asyncio
import json
import threading

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from app.core import auth
from app.core.errors import ApiResponse
from app.engine.react_loop import AgentLoop
from app.engine.tracer import Tracer

router = APIRouter()
_loop = AgentLoop()
_tracer = Tracer()


class ChatRequest(BaseModel):
    message: str
    session_id: str | None = None


@router.post("/chat", response_model=ApiResponse)
def chat(req: ChatRequest, user: dict = Depends(auth.get_current_user)) -> ApiResponse:
    session_id = _tracer.ensure_session(req.session_id, user["user_id"]) if req.session_id else _tracer.start_session(user_id=user["user_id"])
    result = _loop.run(session_id, req.message)
    return ApiResponse(code=0, message="ok", data={"session_id": session_id, **result})


@router.post("/chat/stream")
async def chat_stream(req: ChatRequest, user: dict = Depends(auth.get_current_user)) -> StreamingResponse:
    """SSE 流式：实时推送意图、工具调用、最终答案等过程事件。"""
    queue: asyncio.Queue = asyncio.Queue()
    session_id = _tracer.ensure_session(req.session_id, user["user_id"]) if req.session_id else _tracer.start_session(user_id=user["user_id"])

    def on_event(e: dict) -> None:
        queue.put_nowait(e)

    def worker() -> None:
        _loop.run(session_id, req.message, on_event)
        queue.put_nowait(None)  # 结束标记

    threading.Thread(target=worker, daemon=True).start()

    async def gen():
        yield f"data: {json.dumps({'type': 'session', 'session_id': session_id}, ensure_ascii=False)}\n\n"
        while True:
            e = await queue.get()
            if e is None:
                break
            yield f"data: {json.dumps(e, ensure_ascii=False, default=str)}\n\n"

    return StreamingResponse(gen(), media_type="text/event-stream")
