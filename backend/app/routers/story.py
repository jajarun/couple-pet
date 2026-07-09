"""剧情副本：每对每天一章，同回合双人抉择——两人都选完才互看，AI 同时写出两个选择的后果。

**推进下一幕是自愈的。** `daily.py` 用 `len(answers) == 2` 判断"第二个人到齐"，但两人几乎同时
提交时各自事务只看得见自己 flush 的那条（MySQL InnoDB 默认 REPEATABLE READ 快照隔离），
两边都数到 1。每日一问顶多少落一条时间线事件，剧情副本却会**永远卡住不再续写**。
所以 `_advance_if_ready` 在 `POST /story/choose`（快路径）和 `GET /story`（自愈路径）里都调：
就算写路径两边都数到 1，下一次任何一方轮询都会把缺的那一幕补上。
"""

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app import evolution_service, push_service, streak_service
from app.ai import story as ai_story
from app.ai.prompt import format_tone
from app.config import settings
from app.db import get_db
from app.deps import get_active_couple, get_current_user
from app.models import Avatar, Couple, Event, Story, StoryChoice, StoryRound, User
from app.rules import streak
from app.time_utils import utcnow

router = APIRouter(tags=["story"])

STALE_ROUND_DETAIL = "stale_round"


class ChoiceIn(BaseModel):
    round_no: int
    option_index: int
    client_key: str


def _today():
    return streak.today_for(utcnow(), settings.streak_utc_offset_hours)


def _seed(couple: Couple, day) -> int:
    return day.toordinal() + couple.id


def _players(db: Session, couple: Couple) -> list[dict]:
    """两个人 + 各自「在对方眼里被养成的样子」，揉进 prompt，让故事像是在写他们俩。"""
    out: list[dict] = []
    for uid in (couple.user_a_id, couple.user_b_id):
        if uid is None:
            continue
        u = db.get(User, uid)
        if u is None:
            continue
        av = (
            db.query(Avatar)
            .filter(Avatar.couple_id == couple.id, Avatar.subject_user_id == uid)
            .first()
        )
        pet_title, tone = "", ""
        if av is not None:
            view = evolution_service.build_view(av)
            pet_title = view["title"] if view["stage"] >= 2 else ""  # 没到成体就还没定型
            tone = format_tone((av.persona or {}).get("tone"))
        out.append(
            {"id": u.id, "nickname": u.nickname, "gender": u.gender,
             "pet_title": pet_title, "tone": tone}
        )
    return out


def _rounds(db: Session, story_id: int) -> list[StoryRound]:
    return (
        db.query(StoryRound)
        .filter(StoryRound.story_id == story_id)
        .order_by(StoryRound.round_no)
        .all()
    )


def _round(db: Session, story_id: int, round_no: int) -> StoryRound | None:
    return (
        db.query(StoryRound)
        .filter(StoryRound.story_id == story_id, StoryRound.round_no == round_no)
        .first()
    )


def _choices(db: Session, round_id: int) -> list[StoryChoice]:
    return db.query(StoryChoice).filter(StoryChoice.round_id == round_id).all()


def _get_or_create_story(db: Session, couple: Couple) -> Story:
    """没打完的那章顺延（不看 day）；否则今天开新的一章；今天这章已完结就返回它本身。"""
    active = (
        db.query(Story)
        .filter(Story.couple_id == couple.id, Story.status == "active")
        .order_by(Story.id.desc())
        .first()
    )
    if active is not None:
        return active

    today = _today()
    todays = (
        db.query(Story).filter(Story.couple_id == couple.id, Story.day == today).first()
    )
    if todays is not None:
        return todays  # 今天这章已完结，明天见

    seed = _seed(couple, today)
    title, scene, options, _used_ai = ai_story.generate_opening(_players(db, couple), seed)
    story = Story(
        couple_id=couple.id,
        day=today,
        title=title,
        status="active",
        total_rounds=settings.story_rounds,
    )
    db.add(story)
    db.flush()  # 撞 uq_stories_couple_day 时由 router 的 IntegrityError 重试兜住
    db.add(StoryRound(story_id=story.id, round_no=1, scene=scene, options=options))
    db.flush()
    return story


def _advance_if_ready(db: Session, couple: Couple, story: Story) -> StoryRound | None:
    """两人都选完了就写下一幕。谁调都行（choose 的快路径 / get 的自愈路径），重复调无害。"""
    rounds = _rounds(db, story.id)
    if not rounds:
        return None
    last = rounds[-1]
    if not last.options:
        return None  # 已完结
    chosen = _choices(db, last.id)
    if len(chosen) < 2:
        return None  # 还差一个人
    next_no = last.round_no + 1
    if _round(db, story.id, next_no) is not None:
        return None
    # 竞态窗口就是下面那次 AI 调用的耗时（几秒）：期间对方的轮询 GET 也会走到这里，
    # 于是两边各调一次 AI、一边的 INSERT 撞唯一约束回滚重试。**结果正确，偶尔多烧一次调用**。
    # 不加行锁是有意的——锁住 story 行做 AI 调用，会把对方的 GET 一起阻塞几秒。

    players = _players(db, couple)
    nick = {p["id"]: p["nickname"] for p in players}
    picked = [
        (nick.get(c.user_id, "TA"), last.options[c.option_index])
        for c in sorted(chosen, key=lambda c: c.user_id)  # 定序，prompt 才可复现
    ]
    history = [r.scene for r in rounds]
    seed = _seed(couple, story.day)

    if next_no > story.total_rounds:
        scene, _used = ai_story.generate_ending(story.title, history, picked, players, seed)
        options: list[str] = []
    else:
        scene, options, _used = ai_story.generate_continuation(
            story.title, history, picked, next_no, players, seed
        )

    new_round = StoryRound(story_id=story.id, round_no=next_no, scene=scene, options=options)
    db.add(new_round)
    db.flush()  # 撞 uq_story_rounds_story_round → 外层回滚重试，届时上面那句会直接 return

    if not options:  # 结局幕：收官，往时间线上留个纪念
        story.status = "ended"
        story.ended_at = utcnow()
        db.add(
            Event(
                couple_id=couple.id,
                actor_user_id=None,
                kind="story",
                action_type="ended",
                content=story.title,
                client_key=f"story-{story.id}",  # (couple, client_key, kind) 唯一 → 只落一条
            )
        )
        db.flush()
    return new_round


def _build_response(db: Session, couple: Couple, user: User, story: Story) -> dict:
    partner_id = push_service.partner_of(couple, user.id)
    rounds = []
    for r in _rounds(db, story.id):
        picked = {c.user_id: c.option_index for c in _choices(db, r.id)}
        mine = picked.get(user.id)
        theirs = picked.get(partner_id) if partner_id is not None else None
        both = mine is not None and theirs is not None
        rounds.append(
            {
                "round_no": r.round_no,
                "scene": r.scene,
                "options": list(r.options),
                "my_choice": mine,
                # 都选完才互看对方选了啥（同每日一问的解锁范式，免得跟风）
                "partner_choice": theirs if both else None,
                "both_chose": both,
            }
        )
    last = rounds[-1] if rounds else None
    return {
        "story": {
            "id": story.id,
            "title": story.title,
            "day": story.day.isoformat(),
            "status": story.status,
            "total_rounds": story.total_rounds,
        },
        "rounds": rounds,
        "my_turn": bool(last and last["options"] and last["my_choice"] is None),
    }


@router.get("/story")
def get_story(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    couple = get_active_couple(db, user)
    if couple is None:
        raise HTTPException(status.HTTP_409_CONFLICT, "no active couple")

    def _run():
        story = _get_or_create_story(db, couple)
        _advance_if_ready(db, couple, story)  # 自愈：写路径漏掉的那一幕在这里补上
        resp = _build_response(db, couple, user, story)
        db.commit()
        return resp

    try:
        return _run()
    except IntegrityError:
        # 双方几乎同时首次拉剧情 → 都判断"今日无章"→ 都插入 → 撞 uq_stories_couple_day。
        # 也可能是双方同时自愈同一幕 → 撞 uq_story_rounds_story_round。
        # 回滚重试一次：对方提交的行此时可见，两处都会走"直接查到 → 不再插入"的分支。
        db.rollback()
        return _run()


@router.post("/story/choose")
def choose(
    body: ChoiceIn,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    couple = get_active_couple(db, user)
    if couple is None:
        raise HTTPException(status.HTTP_409_CONFLICT, "no active couple")

    def _run():
        story = _get_or_create_story(db, couple)
        rounds = _rounds(db, story.id)
        last = rounds[-1] if rounds else None
        # 只能选「最后那一幕」，且它得还有选项（结局幕没得选）
        if last is None or last.round_no != body.round_no or not last.options:
            raise HTTPException(status.HTTP_409_CONFLICT, STALE_ROUND_DETAIL)
        if not 0 <= body.option_index < len(last.options):
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "unknown option")

        mine = (
            db.query(StoryChoice)
            .filter(StoryChoice.round_id == last.id, StoryChoice.user_id == user.id)
            .first()
        )
        if mine is not None:  # 幂等：首选锁定，重放不改
            resp = _build_response(db, couple, user, story)
            db.commit()
            return resp

        db.add(
            StoryChoice(
                round_id=last.id,
                user_id=user.id,
                option_index=body.option_index,
                client_key=body.client_key,
            )
        )
        db.flush()
        streak_service.do_touch(db, couple, user.id)  # 做选择算今日露面

        first_chooser = len(_choices(db, last.id)) == 1
        partner_id = push_service.partner_of(couple, user.id)  # commit 前取成 int
        new_round = _advance_if_ready(db, couple, story)

        resp = _build_response(db, couple, user, story)
        db.commit()

        if partner_id is not None:
            if new_round is not None:
                body_text = (
                    f"你俩的选择有了结果，《{story.title}》推进了 🎭"
                    if story.status == "active"
                    else f"《{story.title}》完结了，快去看结局 🎭"
                )
                background_tasks.add_task(
                    push_service.send_to_user,
                    partner_id,
                    {"title": "🎭 剧情副本", "body": body_text, "url": "/", "tag": "story"},
                )
            elif first_chooser:
                background_tasks.add_task(
                    push_service.send_to_user,
                    partner_id,
                    {
                        "title": "🎭 剧情副本",
                        "body": "TA 已经做出选择了，就等你 👀",
                        "url": "/",
                        "tag": "story",
                    },
                )
        return resp

    try:
        return _run()
    except IntegrityError:
        # 并发撞车：重复提交撞 uq_story_choices_round_user，或双方同时推进撞 uq_story_rounds。
        # 回滚重试一次：选择/新幕此时都已可见，分别走"existing 幂等"和"直接查到"分支。
        db.rollback()
        return _run()
