import random

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app import push_service, streak_service
from app.ai.deepseek import generate_reaction
from app.ai.quota import ai_quota_available, record_ai_usage
from app.config import settings
from app.db import get_db
from app.deps import get_active_couple, get_current_user
from app.models import Avatar, CoupleStats, Event, User
from app.rules.actions import ACTION_TYPES, LOCAL_REACTIONS, NUDGE_LINES, apply_action
from app.rules.stats import apply_time_decay, needs_comfort
from app.time_utils import utcnow

router = APIRouter(tags=["actions"])

# 兜底本地文案（AI 动作超额度时用）
_AI_FALLBACK = ["（分身正在充电，先甩你个白眼~）", "（本尊今日营业已满，明天再怼你）"]

_COMFORT_NARRATION = "⚠️ 委屈值爆表啦——TA 在角落画圈圈，快去哄哄（喂口狗粮/抱一个/道个歉）~"

# 对方发动作时给 TA（另一半）推的一句话
_ACTION_PUSH = {
    "scold": "TA 骂你了 😤",
    "poke": "TA 戳了你一下 👉",
    "feed_dogfood": "TA 喂了你狗粮 🍖",
    "hug": "TA 抱了你一下 🤗",
    "miss_you": "TA 说想你了 🥺",
    "apologize": "TA 跟你道歉了 🙇",
    "chat": "TA 找你唠嗑 💬",
}


class ActionIn(BaseModel):
    action_type: str
    content: str = Field("", max_length=1000)
    client_key: str


def event_out(ev: Event) -> dict:
    return {
        "id": ev.id,
        "couple_id": ev.couple_id,
        "actor_user_id": ev.actor_user_id,
        "kind": ev.kind,
        "action_type": ev.action_type,
        "content": ev.content,
        "parent_event_id": ev.parent_event_id,
        "created_at": ev.created_at.isoformat() + "Z",
    }


def _bundle(db: Session, couple_id: int, action_event: Event, stats: dict) -> dict:
    children = (
        db.query(Event)
        .filter(Event.parent_event_id == action_event.id)
        .order_by(Event.id)
        .all()
    )
    events = [action_event] + children
    return {"events": [event_out(e) for e in events], "stats": stats}


def _recent_context(db: Session, couple_id: int, user_id: int, n: int) -> list[dict]:
    """这个饲养者跟这只分身的对话（TA 自己发起的动作 + 其回应子事件），升序，
    映射成 prompt 上下文。按线程隔离——不混入 couple 里另一只分身的对话。"""
    actions = (
        db.query(Event)
        .filter(
            Event.couple_id == couple_id,
            Event.kind == "action",
            Event.actor_user_id == user_id,
        )
        .order_by(Event.id.desc())
        .limit(n)
        .all()
    )
    actions = list(reversed(actions))  # ascending
    if not actions:
        return []
    action_ids = [a.id for a in actions]
    children = (
        db.query(Event)
        .filter(Event.parent_event_id.in_(action_ids), Event.kind != "system")
        .order_by(Event.id)
        .all()
    )
    children_by_parent: dict[int, list] = {}
    for c in children:
        children_by_parent.setdefault(c.parent_event_id, []).append(c)
    out: list[dict] = []
    for a in actions:
        out.append(
            {"speaker": "对方", "text": a.content or (f"（{a.action_type}）" if a.action_type else "")}
        )
        for c in children_by_parent.get(a.id, []):
            out.append({"speaker": "分身", "text": c.content or ""})
    return out[-n:]  # 限最近 n 轮，控制 prompt 大小


@router.post("/actions")
def do_action(
    body: ActionIn,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    if body.action_type not in ACTION_TYPES:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "unknown action")
    couple = get_active_couple(db, user)
    if couple is None:
        raise HTTPException(status.HTTP_409_CONFLICT, "no active couple")

    # 幂等：同一 (couple, client_key) 直接返回既有 bundle
    existing = (
        db.query(Event)
        .filter(
            Event.couple_id == couple.id,
            Event.client_key == body.client_key,
            Event.kind == "action",
        )
        .first()
    )
    if existing is not None:
        cs = db.get(CoupleStats, couple.id)
        return _bundle(db, couple.id, existing, cs.stats)

    pet = (
        db.query(Avatar)
        .filter(Avatar.couple_id == couple.id, Avatar.keeper_user_id == user.id)
        .first()
    )
    cs = db.get(CoupleStats, couple.id)

    now = utcnow()
    elapsed = (now - cs.stats_updated_at).total_seconds()
    decayed = apply_time_decay(cs.stats, elapsed)
    new_stats, needs_ai, local_reaction = apply_action(decayed, body.action_type)

    # 「分身回复」关掉时分身彻底不接话（AI 和本地文案都不出），把话头留给「本尊回应」。
    # 顺带一分 AI 额度都不烧——压根不查 quota。
    if not user.ai_reply_enabled:
        reaction_text = None
    elif needs_ai:
        if ai_quota_available(user, db):
            recent = _recent_context(db, couple.id, user.id, settings.deepseek_recent_context)
            # 分身代表 subject（也就是 TA）——把 TA 的性别喂进人设，让口吻更像本人
            subject = db.get(User, pet.subject_user_id)
            persona = {**(pet.persona or {}), "gender": subject.gender if subject else None}
            reaction_text, used_ai = generate_reaction(
                persona, new_stats, body.action_type, body.content, recent, pet.memory_summary
            )
            if used_ai:
                record_ai_usage(user, db)
        else:
            reaction_text = random.choice(_AI_FALLBACK)
    else:
        reaction_text = local_reaction

    cs.stats = new_stats
    cs.stats_updated_at = now
    action_event = Event(
        couple_id=couple.id,
        actor_user_id=user.id,
        kind="action",
        action_type=body.action_type,
        content=body.content,
        client_key=body.client_key,
    )
    db.add(action_event)
    db.flush()  # assign action_event.id for the children
    if reaction_text is not None:
        db.add(
            Event(
                couple_id=couple.id,
                actor_user_id=None,
                kind="ai_reaction",
                action_type=body.action_type,
                content=reaction_text,
                parent_event_id=action_event.id,
            )
        )

    if needs_comfort(new_stats):
        db.add(
            Event(
                couple_id=couple.id,
                actor_user_id=None,
                kind="system",
                content=_COMFORT_NARRATION,
                parent_event_id=action_event.id,
            )
        )

    streak_service.do_touch(db, couple, user.id)
    db.commit()
    db.refresh(action_event)

    # 隔空撩拨：给对方推一条（commit 后异步发，不阻塞响应）。委屈爆表是更强的召回信号，
    # 合并成一条发（同发一个人时不双响），tag 让 SW 端折叠。partner 需在此刻同步取成 int。
    partner_id = push_service.partner_of(couple, user.id)
    if partner_id is not None:
        if needs_comfort(new_stats):
            payload = {
                "title": "🥺 委屈值爆表",
                "body": "TA 那边委屈到爆表啦，快回去哄哄——喂口狗粮/抱一个/道个歉",
                "url": "/",
                "tag": "comfort",
            }
        else:
            payload = {
                "title": "💕 TA 找你啦",
                "body": _ACTION_PUSH.get(body.action_type, "TA 找你啦"),
                "url": "/",
                "tag": "action",
            }
        background_tasks.add_task(push_service.send_to_user, partner_id, payload)

    return _bundle(db, couple.id, action_event, new_stats)


@router.post("/nudge")
def nudge(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """页面开着时前端约每分钟轮询一次：闲够了就让分身主动撩饲养者一下。
    结合当前数值心情 + subject 的性别/人设生成。返回 {"event": ...} 或 {"event": None}。"""
    couple = get_active_couple(db, user)
    if couple is None:
        return {"event": None}

    last = (
        db.query(Event)
        .filter(Event.couple_id == couple.id)
        .order_by(Event.id.desc())
        .first()
    )
    now = utcnow()
    if last is not None and (now - last.created_at).total_seconds() < settings.nudge_idle_seconds:
        return {"event": None}  # 刚有动静，别打扰

    pet = (
        db.query(Avatar)
        .filter(Avatar.couple_id == couple.id, Avatar.keeper_user_id == user.id)
        .first()
    )
    if pet is None or pet.name == "":
        return {"event": None}  # 分身还没捏出来

    cs = db.get(CoupleStats, couple.id)
    subject = db.get(User, pet.subject_user_id)
    persona = {**(pet.persona or {}), "gender": subject.gender if subject else None}

    if settings.deepseek_api_key and ai_quota_available(user, db):
        recent = _recent_context(db, couple.id, user.id, settings.deepseek_recent_context)
        text, used_ai = generate_reaction(
            persona, cs.stats, "nudge", "", recent, pet.memory_summary
        )
        if used_ai:
            record_ai_usage(user, db)
    else:
        text = random.choice(NUDGE_LINES)

    # actor 记成 subject（分身代表的人）——前端据此把主动消息定位到对应饲养者、摆到左侧
    ev = Event(
        couple_id=couple.id,
        actor_user_id=pet.subject_user_id,
        kind="ai_reaction",
        action_type="nudge",
        content=text,
        parent_event_id=None,
    )
    db.add(ev)
    db.commit()
    db.refresh(ev)
    return {"event": event_out(ev)}
