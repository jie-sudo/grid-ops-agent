from fastapi import APIRouter

from app.config import get_settings
from app.core.errors import ApiResponse

router = APIRouter()


def _check_postgres() -> str:
    settings = get_settings()
    try:
        from sqlalchemy import create_engine, text

        engine = create_engine(settings.database_url, pool_pre_ping=True)
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        engine.dispose()
        return "ok"
    except Exception:
        return "down"


def _check_chroma() -> str:
    settings = get_settings()
    try:
        import chromadb

        client = chromadb.HttpClient(host=settings.chroma_host, port=settings.chroma_port)
        client.heartbeat()
        return "ok"
    except Exception:
        return "down"


async def _check_redis() -> str:
    settings = get_settings()
    try:
        import redis.asyncio as aioredis

        r = aioredis.from_url(settings.redis_url)
        await r.ping()
        await r.aclose()
        return "ok"
    except Exception:
        return "down"


@router.get("/health", response_model=ApiResponse)
async def health() -> ApiResponse:
    return ApiResponse(
        code=0,
        message="ok",
        data={
            "status": "up",
            "dependencies": {
                "postgres": _check_postgres(),
                "chromadb": _check_chroma(),
                "redis": await _check_redis(),
            },
        },
    )
