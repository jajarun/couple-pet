"""每日一问：每对每天一道混味题；双方都答完才解锁对方答案，解锁时落 daily_qa 时间线。"""

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app import push_service, streak_service
from app.ai import daily_question as ai_daily
from app.config import settings
from app.db import get_db
from app.deps import get_active_couple, get_current_user
from app.models import Couple, CoupleStats, DailyAnswer, DailyQuestion, Event, User
from app.rules import daily_questions, streak
from app.time_utils import utcnow

router = APIRouter(tags=["daily"])


class AnswerIn(BaseModel):
    content: str = Field(..., min_length=1, max_length=1000)
    client_key: str


def _today():
    return streak.today_for(utcnow(), settings.streak_utc_offset_hours)


def _get_or_create_question(db: Session, couple: Couple) -> DailyQuestion:
    today = _today()
    q = (
        db.query(DailyQuestion)
        .filter(DailyQuestion.couple_id == couple.id, DailyQuestion.day == today)
        .first()
    )
    if q is not None:
        return q
    # 按天定味 + 避开最近若干天的题，避免短期重复
    seed = today.toordinal() + couple.id
    flavor = daily_questions.choose_flavor(seed)
    recent = {
        r.question
        for r in db.query(DailyQuestion)
        .filter(DailyQuestion.couple_id == couple.id)
        .order_by(DailyQuestion.day.desc())
        .limit(20)
        .all()
    }
    # AI 出题（无 key / 失败自动回落 daily_questions 本地题库）；每对每天一次，不占个人 AI 额度
    text, _used_ai = ai_daily.generate_question(flavor, recent, seed)
    q = DailyQuestion(couple_id=couple.id, day=today, question=text, flavor=flavor)
    db.add(q)
    db.flush()
    return q


def _answer_of(db: Session, question_id: int, user_id: int) -> DailyAnswer | None:
    return (
        db.query(DailyAnswer)
        .filter(DailyAnswer.question_id == question_id, DailyAnswer.user_id == user_id)
        .first()
    )


def _build_response(db: Session, couple: Couple, user: User, q: DailyQuestion) -> dict:
    partner_id = couple.user_b_id if couple.user_a_id == user.id else couple.user_a_id
    mine = _answer_of(db, q.id, user.id)
    partner = _answer_of(db, q.id, partner_id) if partner_id is not None else None
    both = mine is not None and partner is not None
    return {
        "question": {"text": q.question, "flavor": q.flavor},
        "my_answer": mine.content if mine else None,
        "partner_answer": partner.content if (both and partner) else None,
        "both_answered": both,
        "streak": streak_service.build_view(db, couple, user.id),
    }


@router.get("/daily")
def get_daily(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    couple = get_active_couple(db, user)
    if couple is None:
        raise HTTPException(status.HTTP_409_CONFLICT, "no active couple")

    def _run():
        q = _get_or_create_question(db, couple)
        resp = _build_response(db, couple, user, q)
        db.commit()  # 可能新建了题 / streak 行
        return resp

    try:
        return _run()
    except IntegrityError:
        # 双方几乎同时首次拉题：都判断"今日无题"→都插入→撞 uq_daily_questions_couple_day。
        # 回滚后重试一次：对方已提交的题行此时可见，_get_or_create_question 会直接查到它，不再插入。
        db.rollback()
        return _run()


@router.post("/daily/answer")
def answer_daily(
    body: AnswerIn,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    couple = get_active_couple(db, user)
    if couple is None:
        raise HTTPException(status.HTTP_409_CONFLICT, "no active couple")

    def _run():
        q = _get_or_create_question(db, couple)

        existing = _answer_of(db, q.id, user.id)
        if existing is not None:
            resp = _build_response(db, couple, user, q)   # 幂等：首答锁定
            db.commit()
            return resp

        db.add(
            DailyAnswer(
                question_id=q.id, user_id=user.id, content=body.content, client_key=body.client_key
            )
        )
        db.flush()
        streak_service.do_touch(db, couple, user.id)      # 答题算有效互动

        # 若这是第二个答的人 → 双方齐了 → 落 daily_qa 时间线（只落一次）
        answers = db.query(DailyAnswer).filter(DailyAnswer.question_id == q.id).all()
        # 我是第一个答的人 → 答完后催对方来答、好解锁互看（partner 在 commit 前取成 int）
        first_answer = len(answers) == 1
        partner_id = push_service.partner_of(couple, user.id)
        if len(answers) == 2:
            parent = Event(
                couple_id=couple.id,
                actor_user_id=None,
                kind="daily_qa",
                content=q.question,
                parent_event_id=None,
            )
            db.add(parent)
            db.flush()
            for a in answers:
                db.add(
                    Event(
                        couple_id=couple.id,
                        actor_user_id=a.user_id,
                        kind="daily_qa",
                        content=a.content,
                        parent_event_id=parent.id,
                    )
                )

        resp = _build_response(db, couple, user, q)
        db.commit()

        if first_answer and partner_id is not None:
            background_tasks.add_task(
                push_service.send_to_user,
                partner_id,
                {
                    "title": "📩 今日一问",
                    "body": "TA 已经答完今天的每日一问啦，就等你了 👀",
                    "url": "/",
                    "tag": "daily",
                },
            )
        return resp

    try:
        return _run()
    except IntegrityError:
        # 并发撞车：可能是首建题撞 uq_daily_questions_couple_day，也可能是重复答题
        # 撞 uq_daily_answers_question_user（同一 client_key 的重放请求几乎同时到达）。
        # 回滚后重试一次：题/答案此时都已可见，会分别走"直接查到"和"existing 幂等"分支。
        db.rollback()
        return _run()


_RESCUE_INTIMACY_COST = 5


@router.post("/streak/rescue")
def rescue_streak(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    couple = get_active_couple(db, user)
    if couple is None:
        raise HTTPException(status.HTTP_409_CONFLICT, "no active couple")
    if not streak_service.do_rescue(db, couple, user.id):
        raise HTTPException(status.HTTP_409_CONFLICT, "cannot rescue")
    cs = db.get(CoupleStats, couple.id)
    if cs is not None:
        s = dict(cs.stats)
        s["intimacy"] = max(0, s.get("intimacy", 0) - _RESCUE_INTIMACY_COST)
        cs.stats = s
    view = streak_service.build_view(db, couple, user.id)
    db.commit()
    return view
