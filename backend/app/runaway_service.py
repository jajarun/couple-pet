"""离家出走的 DB 编排：三态从事件流派生，零新字段。事务由调用方掌管（不 commit）。

runaway / coax / forgive 三种事件的 actor_user_id 都记成 **keeper**（谁在养这只分身）：
- coax 走 /actions，actor 天然就是 keeper；
- runaway 由 /actions 里那第 5 次骂当场落，显式写成 keeper；
- forgive 是**对方**（分身代表的那个人）点的头，也显式写成 keeper——它标记的是
  「这只分身的事」，不是「谁按的按钮」。
于是同一把钥匙（couple_id + actor=keeper）把三者串起来，两只镜像分身天然隔离、可独立出走。
"""

from datetime import timedelta

from sqlalchemy import case, func, select

from app.models import Event
from app.rules import runaway

_MARKERS = ("runaway", "coax", "forgive")


def pet_state(db, couple_id: int, keeper_id: int) -> str:
    """这只分身此刻 home / away / pending。一次条件聚合，不做三次查询。"""
    row = db.execute(
        select(
            func.max(case((Event.action_type == "runaway", Event.id))).label("runaway_id"),
            func.max(case((Event.action_type == "coax", Event.id))).label("coax_id"),
            func.max(case((Event.action_type == "forgive", Event.id))).label("forgive_id"),
        ).where(
            Event.couple_id == couple_id,
            Event.actor_user_id == keeper_id,
            Event.action_type.in_(_MARKERS),
        )
    ).one()
    return runaway.state_of(row.runaway_id, row.coax_id, row.forgive_id)


def is_pet_away(db, couple_id: int, keeper_id: int) -> bool:
    """它还没回家——跑了，或者哄过了但对方还没点头。"""
    return pet_state(db, couple_id, keeper_id) != runaway.HOME


def recent_treatment(db, couple_id: int, keeper_id: int, now) -> tuple[int, int]:
    """窗口内这个饲养者对这只分身的 (敌意动作数, 安抚动作数)。一次查询。"""
    since = now - timedelta(hours=runaway.WINDOW_HOURS)
    row = db.execute(
        select(
            func.coalesce(
                func.sum(case((Event.action_type.in_(runaway.HOSTILE), 1), else_=0)), 0
            ).label("hostile"),
            func.coalesce(
                func.sum(case((Event.action_type.in_(runaway.SOOTHE), 1), else_=0)), 0
            ).label("soothe"),
        ).where(
            Event.couple_id == couple_id,
            Event.actor_user_id == keeper_id,
            Event.kind == "action",
            Event.created_at > since,
        )
    ).one()
    return int(row.hostile), int(row.soothe)


def provoked(db, couple_id: int, keeper_id: int, now, pending_action: str | None = None) -> bool:
    """窗口内的对待、外加「此刻这一下还没落库的动作」，够不够把它逼走。

    pending_action 让 /actions 在第 5 次骂**落库之前**就问出答案：它要走就不必再回嘴，
    那次 AI 调用也省了。调用方保证它此刻在家。
    """
    hostile, soothe = recent_treatment(db, couple_id, keeper_id, now)
    if pending_action in runaway.HOSTILE:
        hostile += 1
    elif pending_action in runaway.SOOTHE:
        soothe += 1
    return runaway.should_run_away(hostile, soothe)


def bolt(db, couple_id: int, keeper_id: int, note: str) -> Event:
    """它走了，留下一张纸条。不 commit。"""
    ev = Event(
        couple_id=couple_id,
        actor_user_id=keeper_id,
        kind="system",
        action_type="runaway",
        content=note,
    )
    db.add(ev)
    db.flush()
    return ev


def forgive(db, couple_id: int, keeper_id: int, text: str) -> Event:
    """对方点头了。不 commit——id 一旦大过最后那条 coax，pet_state 自己就翻回 home。"""
    ev = Event(
        couple_id=couple_id,
        actor_user_id=keeper_id,
        kind="system",
        action_type="forgive",
        content=text,
    )
    db.add(ev)
    db.flush()
    return ev


def latest_note(db, couple_id: int, keeper_id: int) -> str | None:
    """它留下的那张纸条（最新一条 runaway 事件的 content）。"""
    ev = (
        db.query(Event)
        .filter(
            Event.couple_id == couple_id,
            Event.actor_user_id == keeper_id,
            Event.action_type == "runaway",
        )
        .order_by(Event.id.desc())
        .first()
    )
    return ev.content if ev else None
