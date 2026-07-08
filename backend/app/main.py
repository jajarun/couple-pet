import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.config import settings
from app.routers import actions, auth, avatars, couples, daily, events, push

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # 火苗定时提醒：仅在启用了 Web Push（配了 VAPID 私钥）时才起 scheduler。
    # 注意：scheduler 跑在 uvicorn 进程内，依赖「单 worker」。若改 `--workers N` /
    # gunicorn 多进程，定时会每进程各触发一次 → 重复推送，届时须改哨兵或加分布式锁。
    scheduler = None
    if settings.vapid_private_key:
        try:
            from apscheduler.schedulers.asyncio import AsyncIOScheduler
            from apscheduler.triggers.cron import CronTrigger

            from app import push_scheduler

            scheduler = AsyncIOScheduler(timezone="UTC")
            # streak_reminder_hour 是火苗日界时区（UTC+8）下的小时，换算成 UTC 触发。
            utc_hour = (
                settings.streak_reminder_hour - settings.streak_utc_offset_hours
            ) % 24
            scheduler.add_job(
                push_scheduler.remind_dying_streaks,
                CronTrigger(hour=utc_hour, minute=0),
                id="remind_dying_streaks",
            )
            # 每日一问催答：daily_reminder_hours（UTC+8）各换算成 UTC 触发一次。
            daily_utc_hours = [
                (h - settings.streak_utc_offset_hours) % 24
                for h in settings.daily_reminder_hour_list
            ]
            for h in daily_utc_hours:
                scheduler.add_job(
                    push_scheduler.remind_unanswered_daily,
                    CronTrigger(hour=h, minute=0),
                    id=f"remind_daily_{h}",
                )
            scheduler.start()
            logger.info(
                "reminder scheduler started (streak UTC hour=%s, daily UTC hours=%s)",
                utc_hour,
                daily_utc_hours,
            )
        except Exception as e:  # scheduler 起不来不该拖垮整个后端
            logger.warning("failed to start scheduler: %s", e)
            scheduler = None
    yield
    if scheduler is not None:
        scheduler.shutdown(wait=False)


app = FastAPI(title="AI Couple Pet Game API", lifespan=lifespan)

app.include_router(auth.router)
app.include_router(couples.router)
app.include_router(avatars.router)
app.include_router(actions.router)
app.include_router(events.router)
app.include_router(daily.router)
app.include_router(push.router)


@app.get("/health")
def health():
    return {"status": "ok"}
