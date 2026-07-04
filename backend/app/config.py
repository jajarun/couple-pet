from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # 生产用 MySQL，例如 mysql+pymysql://user:pass@host:3306/petgame
    database_url: str = "sqlite:///./dev.db"
    jwt_secret: str = "dev-secret-change-me"
    daily_chat_cap: int = 50
    deepseek_api_key: str = ""
    # 空 key = 走本地兜底（dev/CI 离线）。key 只在服务端，前端永不可见。
    deepseek_base_url: str = "https://api.deepseek.com"
    deepseek_model: str = "deepseek-chat"
    deepseek_timeout_seconds: int = 8
    deepseek_max_tokens: int = 200
    deepseek_temperature: float = 1.3
    deepseek_recent_context: int = 10  # 喂进 prompt 的最近事件条数


settings = Settings()
