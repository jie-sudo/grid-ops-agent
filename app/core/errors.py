from typing import Any

from pydantic import BaseModel


class ApiResponse(BaseModel):
    """统一返回结构：{code, message, data}（对应 SDD 6.2）。"""

    code: int = 0
    message: str = "ok"
    data: Any = None


class ErrorCode:
    """统一错误码（对应 SDD 6.2）。"""

    OK = 0
    BAD_REQUEST = 400
    UNAUTHORIZED = 401
    FORBIDDEN = 403
    NOT_FOUND = 404
    RATE_LIMITED = 429
    INTERNAL = 500
    UPSTREAM_TIMEOUT = 504


class AppError(Exception):
    """业务异常：带错误码，避免向外泄露原始堆栈。"""

    def __init__(self, code: int, message: str) -> None:
        self.code = code
        self.message = message
        super().__init__(message)
