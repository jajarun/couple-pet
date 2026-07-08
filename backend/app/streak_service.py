"""火苗的 DB 编排：行↔纯函数 state 转换、槽位、touch/view + 里程碑事件。事务由 router 掌管（不 commit）。"""

from app.config import settings
from app.models import CoupleStreak, Event
from app.rules import streak
from app.time_utils import utcnow

_STATE_KEYS = ("count", "last_both_day", "a_active_day", "b_active_day", "rescue_day")

MILESTONES = {7, 30, 100, 365}
_MILESTONE_TEXT = {
    7: "🔥 火苗满 7 天啦——一周没断，这份坚持有点甜。",
    30: "🔥 火苗 30 天！整整一个月天天见，厉害了。",
    100: "🔥 火苗破 100 天！这是要处成传说啊。",
    365: "🔥 火苗满一年！365 天没断过，离谱又浪漫。",
}


def slot_for(couple, user_id: int) -> str:
    return "a" if couple.user_a_id == user_id else "b"


def get_or_create_row(db, couple_id: int) -> CoupleStreak:
    row = db.get(CoupleStreak, couple_id)
    if row is None:
        row = CoupleStreak(couple_id=couple_id, count=0)
        db.add(row)
        db.flush()
    return row


def _row_to_state(row: CoupleStreak) -> dict:
    return {k: getattr(row, k) for k in _STATE_KEYS}


def _apply_state(row: CoupleStreak, state: dict) -> None:
    for k in _STATE_KEYS:
        setattr(row, k, state[k])


def _today() -> "object":
    return streak.today_for(utcnow(), settings.streak_utc_offset_hours)


def do_touch(db, couple, user_id: int) -> None:
    row = get_or_create_row(db, couple.id)
    before = row.count
    _apply_state(row, streak.touch(_row_to_state(row), slot_for(couple, user_id), _today()))
    after = row.count
    if after > before and after in MILESTONES:  # 跨过里程碑 → 落一条系统庆祝
        db.add(
            Event(
                couple_id=couple.id,
                actor_user_id=None,
                kind="system",
                content=_MILESTONE_TEXT[after],
            )
        )


def build_view(db, couple, user_id: int) -> dict:
    row = get_or_create_row(db, couple.id)
    v = streak.view(_row_to_state(row), slot_for(couple, user_id), _today())
    lag = v.pop("lagging_slot")
    lagging_user_id = None
    if lag == "a":
        lagging_user_id = couple.user_a_id
    elif lag == "b":
        lagging_user_id = couple.user_b_id
    return {**v, "lagging_user_id": lagging_user_id}
