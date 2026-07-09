"""分身「自己的生活」定时 job：让它在你不看的时候也活着。

跟 push_scheduler.py 分开：那个文件是「推送提醒」，这个是玩法本身——**没配 VAPID 也要跑**
（发推那一步走 push_service.send_to_user，无私钥自动 no-op，天然安全）。

跑在 uvicorn 进程内（main.py lifespan 的 APScheduler 触发）。自开 SessionLocal。永不抛。
"""

import logging

from sqlalchemy.exc import IntegrityError

from app import push_service, runaway_service
from app.ai.dream import generate_dream, generate_runaway_note
from app.config import settings
from app.db import SessionLocal
from app.models import Avatar, Couple, CoupleStats, Event, User
from app.rules import evolution, runaway, streak
from app.time_utils import utcnow

logger = logging.getLogger(__name__)

_DREAM_PUSH = {
    "title": "🌙 它昨晚说梦话了",
    "body": "你养的那只分身，梦里嘟囔了一句关于你的话。去听听？",
    "url": "/",
    "tag": "dream",
}

_RUNAWAY_PUSH = {
    "title": "🪹 它离家出走了",
    "body": "你养的那只分身受不了了，留了张纸条就跑了。快去把它哄回来。",
    "url": "/",
    "tag": "runaway",
}


def _today():
    return streak.today_for(utcnow(), settings.streak_utc_offset_hours)


def _now():
    return utcnow()


def dream_client_key(avatar_id: int, day) -> str:
    """幂等键。**必须含 avatar_id**——唯一约束是 (couple_id, client_key, kind)，
    同一天两只镜像分身若都用 dream-{day}，第二只会撞约束落不进去。"""
    return f"dream-{avatar_id}-{day.isoformat()}"


def _persona_for(db, avatar: Avatar) -> dict:
    subject = db.get(User, avatar.subject_user_id)
    return {**(avatar.persona or {}), "gender": subject.gender if subject else None}


def _branch_of(avatar: Avatar) -> str:
    evo = evolution.view(avatar.evolution)
    return evo["branch"] if evo["stage"] >= 2 else ""  # 没定型就别按形态说话


def _active_avatars(db, couple: Couple) -> list[Avatar]:
    """这对情侣的两只分身，跳过还没捏出来的。"""
    rows = db.query(Avatar).filter(Avatar.couple_id == couple.id).all()
    return [av for av in rows if av.name != ""]


def _spin_one_dream(db, couple: Couple, avatar: Avatar, stats: dict, day) -> bool:
    """给一只分身落一条梦话。已经有了（重复触发）就跳过。返回是否新落了一条。"""
    seed = day.toordinal() + avatar.id
    text, _used_ai = generate_dream(_persona_for(db, avatar), _branch_of(avatar), stats, seed)
    db.add(
        Event(
            couple_id=couple.id,
            actor_user_id=avatar.subject_user_id,  # actor=subject，同 nudge：落到分身那一侧
            kind="ai_reaction",
            action_type="dream",
            content=text,
            client_key=dream_client_key(avatar.id, day),
        )
    )
    try:
        db.commit()
        return True
    except IntegrityError:
        db.rollback()  # 今天这只已经做过梦了（撞 uq_events_couple_client_key_kind）
        return False


def run_morning_dreams() -> None:
    """每天早上给每只分身生成一句「昨夜梦话」，并提醒它的饲养者来听。

    为什么放早上而不是凌晨：Web Push 会在手机上响，绝不能半夜推。早晨生成、内容讲昨夜，
    用户任何时候打开都看得到，体验无损。
    """
    db = SessionLocal()
    try:
        day = _today()
        for couple in db.query(Couple).filter(Couple.status == "active").all():
            cs = db.get(CoupleStats, couple.id)
            stats = cs.stats if cs else {}
            for avatar in _active_avatars(db, couple):
                try:
                    if _spin_one_dream(db, couple, avatar, stats, day):
                        push_service.send_to_user(avatar.keeper_user_id, _DREAM_PUSH)
                except Exception as e:  # 一只翻车不该拖垮其余
                    logger.warning("dream failed (avatar=%s): %s", avatar.id, e)
                    db.rollback()
    except Exception as e:
        logger.warning("run_morning_dreams crashed: %s", e)
    finally:
        db.close()


def _maybe_run_away(db, couple: Couple, avatar: Avatar, now) -> bool:
    """一只分身够不够委屈到出走。够就落纸条事件。返回是否刚跑掉。"""
    keeper_id = avatar.keeper_user_id
    already_away = runaway_service.is_pet_away(db, couple.id, keeper_id)
    hostile, soothe = runaway_service.recent_treatment(db, couple.id, keeper_id, now)
    if not runaway.should_run_away(hostile, soothe, already_away):
        return False

    note, _used_ai = generate_runaway_note(
        _persona_for(db, avatar), _branch_of(avatar), now.toordinal() + avatar.id
    )
    db.add(
        Event(
            couple_id=couple.id,
            actor_user_id=keeper_id,  # actor=keeper，才能跟 coax 配对（见 runaway_service 顶部）
            kind="system",
            action_type="runaway",
            content=note,
        )
    )
    db.commit()
    return True


def detect_runaways() -> None:
    """每小时扫一遍：谁在近 6 小时里只骂不哄，谁养的分身就留张纸条跑掉。

    跑得勤是必须的——判据看的是滑动窗口内的动作数，窗口一滑过去就不该再触发。
    """
    db = SessionLocal()
    try:
        now = _now()
        for couple in db.query(Couple).filter(Couple.status == "active").all():
            for avatar in _active_avatars(db, couple):
                try:
                    if _maybe_run_away(db, couple, avatar, now):
                        push_service.send_to_user(avatar.keeper_user_id, _RUNAWAY_PUSH)
                except Exception as e:  # 一只翻车不该拖垮其余
                    logger.warning("runaway failed (avatar=%s): %s", avatar.id, e)
                    db.rollback()
    except Exception as e:
        logger.warning("detect_runaways crashed: %s", e)
    finally:
        db.close()
