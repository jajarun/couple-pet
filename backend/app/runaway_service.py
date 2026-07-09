"""离家出走的 DB 编排：出走态从事件流派生，零新字段。事务由调用方掌管（不 commit）。

runaway 和 coax 两种事件的 actor_user_id 都记成 **keeper**（谁在养这只分身）：
- coax 走 /actions，actor 天然就是 keeper；
- runaway 由 detect_runaways 落，显式写成 keeper。
于是同一把钥匙（couple_id + actor=keeper）就能把两者配对，两只镜像分身天然隔离、可独立出走。
"""

from datetime import timedelta

from sqlalchemy import case, func, select

from app.models import Event
from app.rules import runaway

_MARKERS = ("runaway", "coax")


def is_pet_away(db, couple_id: int, keeper_id: int) -> bool:
    """这个饲养者的分身是不是正跑在外面。一次条件聚合，不做两次查询。"""
    row = db.execute(
        select(
            func.max(case((Event.action_type == "runaway", Event.id))).label("runaway_id"),
            func.max(case((Event.action_type == "coax", Event.id))).label("coax_id"),
        ).where(
            Event.couple_id == couple_id,
            Event.actor_user_id == keeper_id,
            Event.action_type.in_(_MARKERS),
        )
    ).one()
    return runaway.is_away(row.runaway_id, row.coax_id)


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
