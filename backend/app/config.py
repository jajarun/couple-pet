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
    nudge_idle_seconds: int = 55  # 距上条事件多久没动静，分身才主动撩你（前端约每分钟轮询一次）
    streak_utc_offset_hours: int = 8  # 火苗日界时区偏移（8=上海，无 DST）
    # Web Push（VAPID）。空 private key = 关闭推送（dev/CI 离线兜底，同 deepseek_api_key 范式）。
    vapid_public_key: str = ""  # 前端订阅要用，走 GET /push/public-key 下发
    vapid_private_key: str = ""  # 只在服务端，前端永不可见
    vapid_subject: str = "mailto:leosmith16879@gmail.com"
    streak_reminder_hour: int = 20  # 每天几点（火苗日界时区，UTC+8）扫一次将熄的火苗并提醒
    # 每日一问催答时刻（火苗日界时区 UTC+8）：逗号分隔多个整点；留空 = 关闭该催答。
    daily_reminder_hours: str = "10,14"

    @property
    def daily_reminder_hour_list(self) -> list[int]:
        """把 daily_reminder_hours 解析成去重、排序的整点列表（无效项忽略）。"""
        out: set[int] = set()
        for part in self.daily_reminder_hours.split(","):
            part = part.strip()
            if not part:
                continue
            try:
                out.add(int(part) % 24)
            except ValueError:
                continue
        return sorted(out)


settings = Settings()
