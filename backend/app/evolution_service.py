"""进化的 DB 编排：把一次饲养动作记进 Avatar.evolution。事务由 router 掌管（不 commit）。"""

from app.models import Avatar
from app.rules import evolution


def bump_care(db, avatar: Avatar, action_type: str, now_iso: str) -> tuple[dict, bool]:
    """记一次饲养者对这只分身的动作，返回 (进化 view, 是否刚进化)。"""
    new_evo, evolved = evolution.evolve(avatar.evolution, action_type, now_iso)
    # JSON 列：整体赋一个新 dict，SQLAlchemy 才认脏（原地改字段不会触发 UPDATE）
    avatar.evolution = new_evo
    db.flush()
    return evolution.view(new_evo), evolved


def build_view(avatar: Avatar) -> dict:
    """只读派生（不落库）。老分身的 evolution 是 {}，view 会归一成一颗蛋。"""
    return evolution.view(avatar.evolution)
