from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # 生产用 MySQL，例如 mysql+pymysql://user:pass@host:3306/petgame
    database_url: str = "sqlite:///./dev.db"
    jwt_secret: str = "dev-secret-change-me"
    daily_chat_cap: int = 50
    deepseek_api_key: str = ""


settings = Settings()
