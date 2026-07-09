import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.config import settings
from app.routers import (
    actions,
    auth,
    avatars,
    couples,
    daily,
    events,
    presence,
    push,
    runaway,
    story,
)

logger = logging.getLogger(__name__)


def _utc_hour(local_hour: int) -> int:
    """把火苗日界时区（UTC+8）下的整点换算成 UTC 整点。"""
    return (local_hour - settings.streak_utc_offset_hours) % 24


def _schedule_gameplay(scheduler, cron) -> None:
    """挂玩法 job（分身梦话）。不依赖推送配置——没 VAPID 也该做梦。

    离家出走没有 job：第 5 次骂落库的那一刻当场生效，长在 POST /actions 的事务里。
    """
    from app import live_scheduler

    scheduler.add_job(
        live_scheduler.run_morning_dreams,
        cron(hour=_utc_hour(settings.dream_hour), minute=0),
        id="run_morning_dreams",
    )


def _schedule_push_reminders(scheduler, cron) -> None:
    """挂推送提醒 job。只在配了 VAPID 私钥时才有意义（否则 send_to_user 是 no-op）。"""
    from app import push_scheduler

    scheduler.add_job(
        push_scheduler.remind_dying_streaks,
        cron(hour=_utc_hour(settings.streak_reminder_hour), minute=0),
        id="remind_dying_streaks",
    )
    for h in settings.daily_reminder_hour_list:
        utc_h = _utc_hour(h)
        scheduler.add_job(
            push_scheduler.remind_unanswered_daily,
            cron(hour=utc_h, minute=0),
            id=f"remind_daily_{utc_h}",
        )


@asynccontextmanager
async def lifespan(app: FastAPI):
    # 注意：scheduler 跑在 uvicorn 进程内，依赖「单 worker」。若改 `--workers N` /
    # gunicorn 多进程，定时会每进程各触发一次 → 重复推送/重复出题，届时须改哨兵或加分布式锁。
    scheduler = None
    if settings.enable_scheduler:
        try:
            from apscheduler.schedulers.asyncio import AsyncIOScheduler
            from apscheduler.triggers.cron import CronTrigger

            scheduler = AsyncIOScheduler(timezone="UTC")
            _schedule_gameplay(scheduler, CronTrigger)
            if settings.vapid_private_key:
                _schedule_push_reminders(scheduler, CronTrigger)
            scheduler.start()
            logger.info(
                "scheduler started (jobs=%s)", [j.id for j in scheduler.get_jobs()]
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
app.include_router(presence.router)
app.include_router(story.router)
app.include_router(runaway.router)
app.include_router(push.router)


@app.get("/health")
def health():
    return {"status": "ok"}
