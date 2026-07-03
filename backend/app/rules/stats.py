"""纯函数：共享关系数值。无 DB / 时钟 / AI / config 依赖。"""

STAT_KEYS = ["grievance", "dogfood", "miss", "intimacy"]

DEFAULT_STATS = {"grievance": 0, "dogfood": 0, "miss": 0, "intimacy": 0}

GRIEVANCE_THRESHOLD = 80

# 每小时时间变化点数；intimacy 不在内（永不随时间变化）
TIME_DELTA_PER_HOUR = {"miss": 4.0, "grievance": -2.0, "dogfood": -1.0}


def clamp(v: float) -> int:
    return int(max(0, min(100, v)))


def apply_time_decay(stats: dict, elapsed_seconds: float) -> dict:
    hours = elapsed_seconds / 3600.0
    out = dict(stats)
    for key, rate in TIME_DELTA_PER_HOUR.items():
        out[key] = clamp(stats[key] + rate * hours)
    return out


def needs_comfort(stats: dict) -> bool:
    return stats["grievance"] >= GRIEVANCE_THRESHOLD
