import random

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app import evolution_service, presence_service, push_service, runaway_service, streak_service
from app.ai.deepseek import generate_reaction
from app.ai.dream import generate_runaway_note
from app.ai.quota import ai_quota_available, record_ai_usage
from app.config import settings
from app.db import get_db
from app.deps import get_active_couple, get_current_user
from app.models import Avatar, CoupleStats, Event, User
from app.rules import runaway
from app.rules.actions import ACTION_TYPES, LOCAL_REACTIONS, NUDGE_LINES, apply_action
from app.rules.stats import apply_time_decay, needs_comfort
from app.time_utils import utcnow

router = APIRouter(tags=["actions"])

# 兜底本地文案（AI 动作超额度时用）
_AI_FALLBACK = ["（分身正在充电，先甩你个白眼~）", "（本尊今日营业已满，明天再怼你）"]

_COMFORT_NARRATION = "⚠️ 委屈值爆表啦——TA 在角落画圈圈，快去哄哄（喂口狗粮/抱一个/道个歉）~"

# 跨过进化阶段时落的旁白（同 streak_service.MILESTONES 的写法）
_EVOLVE_TEXT = {
    1: "🐣 分身破壳啦！它开始认得你了。",
    2: "✨ 分身进化成「成体」——性格就此定型，再也改不回来咯。",
    3: "👑 完全体达成！这只分身被你养到头了。",
}

# 对方发动作时给 TA（另一半）推的一句话。coax 不在这儿——它有自己的推送分支（见下）
_ACTION_PUSH = {
    "scold": "TA 骂你了 😤",
    "poke": "TA 戳了你一下 👉",
    "feed_dogfood": "TA 喂了你狗粮 🍖",
    "hug": "TA 抱了你一下 🤗",
    "miss_you": "TA 说想你了 🥺",
    "apologize": "TA 跟你道歉了 🙇",
    "chat": "TA 找你唠嗑 💬",
    "headpat": "TA 隔空摸了摸你的头 🫳",
}

# 出走三态里、要推给「分身代表的那个人」（也就是发动作者的另一半）的两条。
# 跑掉那一刻不推 keeper——TA 正盯着屏幕，界面当场就换成空窝了。
_BOLTED_PUSH = {
    "title": "🪹 TA 把「你」气跑了",
    "body": "一小时里骂了五次，那只代表你的分身留下纸条就跑了。",
    "url": "/",
    "tag": "runaway",
}
_COAX_PUSH = {
    "title": "🥺 TA 在哄你回家",
    "body": "分身要不要回去，得你点头。",
    "url": "/",
    "tag": "runaway",
}

# 分身跑了，除了「哄」什么都做不了。前端会先切成 RunawayScreen，这里是防多端竞态的兜底。
PET_AWAY_DETAIL = "pet_away"

# 哄过了、正等对方点头：这期间**连「哄」都拦**，否则 coax 的「委屈 −30 / 亲密 +5」
# 能在等待期里无限刷。
AWAITING_FORGIVENESS_DETAIL = "awaiting_forgiveness"

# 摸摸头只在两人同框时存在。前端在对方下线时就把这个键藏了，这里是防多端/直接打接口的兜底。
NOT_TOGETHER_DETAIL = "not_together"
TOGETHER_MULTIPLIER = 2  # 当着面，什么都更疼也更甜


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


def _bundle(
    db: Session,
    couple_id: int,
    action_event: Event,
    stats: dict,
    evo: dict,
    evolved: bool,
    together: bool,
    ran_away: bool = False,
) -> dict:
    children = (
        db.query(Event)
        .filter(Event.parent_event_id == action_event.id)
        .order_by(Event.id)
        .all()
    )
    events = [action_event] + children
    # evolved 让前端放全屏进化动画；evolution 喂给首页的进度条；
    # together 是「TA 此刻在不在」的即时标志（不是这次动作的历史记录），驱动首页的同框态；
    # ran_away = 就是这一下把它逼走的（纸条事件不挂 parent，不在 events 里）→ 前端重取 /avatars/pet
    return {
        "events": [event_out(e) for e in events],
        "stats": stats,
        "evolution": evo,
        "evolved": evolved,
        "together": together,
        "ran_away": ran_away,
    }


def _persona_for(db: Session, pet: Avatar) -> dict:
    """分身代表 subject（也就是 TA）——把 TA 的性别、以及已定型的进化形态喂进人设。

    形态取的是**这次动作之前**的 evolution：回应发生在进化之前，刚破壳那一下不该提前换口吻。
    """
    subject = db.get(User, pet.subject_user_id)
    evo = evolution_service.build_view(pet)
    return {
        **(pet.persona or {}),
        "gender": subject.gender if subject else None,
        "branch": evo["branch"] if evo["stage"] >= 2 else "",  # 没到成体就还没定型
    }


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

    pet = (
        db.query(Avatar)
        .filter(Avatar.couple_id == couple.id, Avatar.keeper_user_id == user.id)
        .first()
    )
    now = utcnow()
    # 只读对方的心跳（心跳只由 POST /presence 写）。同框 = 两人此刻都开着页面。
    together = presence_service.partner_online(db, couple, user.id, now)

    # 幂等：同一 (couple, client_key) 直接返回既有 bundle。**不能再 bump 一次经验**——
    # 重试/连点不该让分身白长一截。
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
        evo = evolution_service.build_view(pet)
        return _bundle(db, couple.id, existing, cs.stats, evo, False, together)

    # 分身跑了就只剩「哄」这一条路；哄完在等对方点头，那连哄都别再点了。
    pet_state = runaway_service.pet_state(db, couple.id, user.id)
    if pet_state == runaway.PENDING:
        raise HTTPException(status.HTTP_409_CONFLICT, AWAITING_FORGIVENESS_DETAIL)
    if pet_state == runaway.AWAY and body.action_type != "coax":
        raise HTTPException(status.HTTP_409_CONFLICT, PET_AWAY_DETAIL)

    # 摸摸头是同框限定：TA 一下线这个键就该消失。放在幂等早返回之后——
    # 同框时发出的那一下，重放时不该因为 TA 刚下线就被打回。
    if body.action_type == "headpat" and not together:
        raise HTTPException(status.HTTP_409_CONFLICT, NOT_TOGETHER_DETAIL)

    cs = db.get(CoupleStats, couple.id)

    elapsed = (now - cs.stats_updated_at).total_seconds()
    decayed = apply_time_decay(cs.stats, elapsed)
    new_stats, needs_ai, local_reaction = apply_action(
        decayed, body.action_type, TOGETHER_MULTIPLIER if together else 1
    )

    # 这一下会不会把它逼走（1 小时内骂满 5 次、一次没哄）。**在 AI 之前问**：
    # 它要走就不回嘴了，那次调用白烧。落库跟这次动作同一个事务，第 5 次骂当场生效。
    bolted = body.action_type in runaway.HOSTILE and runaway_service.provoked(
        db, couple.id, user.id, now, pending_action=body.action_type
    )

    # 「分身回复」关掉时分身彻底不接话（AI 和本地文案都不出），把话头留给「本尊回应」。
    # 顺带一分 AI 额度都不烧——压根不查 quota。
    if bolted or not user.ai_reply_enabled:
        reaction_text = None  # 走了的那一下不回嘴：纸条拍桌上就是它最后一句话
    elif needs_ai:
        if ai_quota_available(user, db):
            recent = _recent_context(db, couple.id, user.id, settings.deepseek_recent_context)
            persona = _persona_for(db, pet)
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

    if bolted:
        # 纸条**不挂 parent**（同进化旁白）：_bundle 只收 action 的子事件，挂上去会跟
        # 「委屈爆表」旁白抢 HomeScreen 的 comfortText。前端靠 bundle.ran_away 换屏。
        persona = _persona_for(db, pet)
        note, _used_ai = generate_runaway_note(persona, persona["branch"], now.toordinal() + pet.id)
        runaway_service.bolt(db, couple.id, user.id, note)

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

    # 记一次饲养：这只分身的进化只由「它的饲养者对它做了什么」推动。
    # 同框不翻倍——care 数的是「做了几次」，翻倍会把分支占比算歪。
    evo_view, evolved = evolution_service.bump_care(db, pet, body.action_type, now.isoformat())
    evolve_text = _EVOLVE_TEXT.get(evo_view["stage"]) if evolved else None
    if evolve_text:
        # 独立事件、**不挂 parent**：_bundle 只收 action 的子事件，挂上去会跟「委屈爆表」旁白
        # 抢 HomeScreen 的 comfortText（它 find 第一条 system）。进化动画走 bundle.evolved。
        db.add(
            Event(
                couple_id=couple.id,
                actor_user_id=None,
                kind="system",
                action_type="evolve",
                content=evolve_text,
            )
        )

    streak_service.do_touch(db, couple, user.id)
    db.commit()
    db.refresh(action_event)

    # 隔空撩拨：给对方推一条（commit 后异步发，不阻塞响应）。委屈爆表是更强的召回信号，
    # 合并成一条发（同发一个人时不双响），tag 让 SW 端折叠。partner 需在此刻同步取成 int。
    partner_id = push_service.partner_of(couple, user.id)
    if partner_id is not None:
        if bolted:
            payload = _BOLTED_PUSH  # 跑掉的那只代表的正是 partner——这一条冲击力最大
        elif body.action_type == "coax":
            payload = _COAX_PUSH  # 回不回家，球在 partner 脚下
        elif needs_comfort(new_stats):
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

    return _bundle(db, couple.id, action_event, new_stats, evo_view, evolved, together, bolted)


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
    if runaway_service.is_pet_away(db, couple.id, user.id):
        return {"event": None}  # 它跑了，撩不了你

    cs = db.get(CoupleStats, couple.id)
    persona = _persona_for(db, pet)

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
