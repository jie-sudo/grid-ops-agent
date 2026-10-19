from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_name: str = "grid-ops-agent"
    debug: bool = False

    # 数据层（管理/只读/读写 三角色分离）
    database_url: str = "postgresql+psycopg://app:app@localhost:5432/gridops"
    database_url_read: str = "postgresql+psycopg://gridops_reader:reader@localhost:5432/gridops"
    database_url_write: str = "postgresql+psycopg://gridops_writer:writer@localhost:5432/gridops"
    chroma_host: str = "localhost"
    chroma_port: int = 8000
    embedding_model: str = ""  # 空=chromadb 默认英文模型；中文可设 "BAAI/bge-small-zh-v1.5"
    redis_url: str = "redis://localhost:6379/0"

    # LLM（OpenAI 兼容，M4 启用）
    llm_base_url: str = ""
    llm_api_key: str = ""
    llm_model: str = "deepseek-chat"

    # 鉴权
    jwt_secret: str = "change-me"
    jwt_expire_minutes: int = 480

    # Agent 引擎
    max_steps: int = 6
    tool_timeout: int = 10
    llm_timeout: int = 30
    max_output_tokens: int = 4096

    # 预算与成本（预留式记账，借鉴 AegisOps BudgetLedger）
    max_tokens_per_run: int = 20000
    max_cost_per_run: float = 0.0  # 0 = 不限费用
    llm_price_rmb_per_mtok: float = 0.0  # 每百万 token 综合单价（元），0 = 不估算费用

    # 历史数据保留（P0：热区月数 + 归档保留开关）
    history_retention_months: int = 36
    history_archive: bool = True  # True=归档保留到 *_archive 表；False=直接删除

    # 数据源（接入真实数据时切换；默认 mock）
    data_source: str = "mock"

    # 限流
    rate_limit_read: int = 60
    rate_limit_write: int = 10


@lru_cache
def get_settings() -> Settings:
    return Settings()
