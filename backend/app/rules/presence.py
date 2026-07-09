"""纯函数：在线判定。无 DB / 时钟 / AI / settings，`now` 与 `ttl` 一律由调用方传入。"""

from datetime import datetime


def is_online(last_seen_at: datetime | None, now: datetime, ttl_seconds: int) -> bool:
    """最后一次心跳还在 ttl 之内就算「TA 正在看」。从没打过心跳（None）= 离线。"""
    if last_seen_at is None:
        return False
    return (now - last_seen_at).total_seconds() <= ttl_seconds
