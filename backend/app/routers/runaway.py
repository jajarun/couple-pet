"""离家出走的收尾：分身跑了、饲养者哄了，**还得它代表的那个人点头**才回得了家。

哄（coax）走 /actions，点头（forgive）走这里——因为按按钮的是「对方」，
而事件仍要记在 keeper 名下（三个标记同一把钥匙，见 runaway_service 顶部）。
"""

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app import push_service, runaway_service, streak_service
from app.db import get_db
from app.deps import get_active_couple, get_current_user
from app.models import Avatar, User
from app.rules import runaway

router = APIRouter(tags=["runaway"])

# TA 压根还没来哄，就别急着大度了。
NOT_PENDING_DETAIL = "not_pending"

_FORGIVEN_PUSH = {
    "title": "💌 TA 原谅你了",
    "body": "分身回家了。这次好好待它。",
    "url": "/",
    "tag": "runaway",
}


@router.post("/runaway/forgive")
def forgive(
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    couple = get_active_couple(db, user)
    if couple is None:
        raise HTTPException(status.HTTP_409_CONFLICT, "no active couple")
    # 跑掉的是「代表我、养在 TA 那儿」的那只 → 这只分身的 keeper 就是对方
    keeper_id = push_service.partner_of(couple, user.id)
    if keeper_id is None:
        raise HTTPException(status.HTTP_409_CONFLICT, "no active couple")

    state = runaway_service.pet_state(db, couple.id, keeper_id)
    if state == runaway.HOME:
        return {"state": runaway.HOME}  # 已经点过头了（连点/多端重放）——幂等，不报错
    if state == runaway.AWAY:
        raise HTTPException(status.HTTP_409_CONFLICT, NOT_PENDING_DETAIL)

    av = (
        db.query(Avatar)
        .filter(Avatar.couple_id == couple.id, Avatar.keeper_user_id == keeper_id)
        .first()
    )
    pet_name = av.name if av is not None and av.name else "分身"
    # 这条系统事件存一份、两个人共读，所以只能用昵称，不能写「你 / TA」
    runaway_service.forgive(db, couple.id, keeper_id, f"💌 {user.nickname}点了头，{pet_name}回家了。")
    streak_service.do_touch(db, couple, user.id)  # 大度也算今日露面
    db.commit()

    background_tasks.add_task(push_service.send_to_user, keeper_id, _FORGIVEN_PUSH)
    return {"state": runaway.HOME}
