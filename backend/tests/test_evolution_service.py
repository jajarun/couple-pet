from app import evolution_service
from app.models import Avatar


def _avatar(db):
    av = Avatar(couple_id=1, subject_user_id=1, keeper_user_id=2, name="狗蛋")
    db.add(av)
    db.flush()
    return av


def test_bump_care_records_action_and_returns_view(client):
    db = client.session_factory()
    try:
        av = _avatar(db)
        view, evolved = evolution_service.bump_care(db, av, "hug", "2026-07-09T12:00:00")
        assert evolved is False
        assert view["exp"] == 3 and view["stage"] == 0
        assert av.evolution["care"] == {"hug": 1}
    finally:
        db.close()


def test_bump_care_flushes_but_does_not_commit(client):
    """事务边界归 router：service 只 flush，回滚要能把这次饲养一起撤掉。"""
    db = client.session_factory()
    try:
        av = _avatar(db)
        db.commit()
        avatar_id = av.id
        evolution_service.bump_care(db, av, "hug", "t")
        db.rollback()
        assert db.get(Avatar, avatar_id).evolution == {}
    finally:
        db.close()


def test_bump_care_persists_json_column(client):
    """JSON 列必须整体赋新 dict，原地改字段 SQLAlchemy 不认脏、UPDATE 发不出去。"""
    db = client.session_factory()
    try:
        av = _avatar(db)
        evolution_service.bump_care(db, av, "scold", "t")
        db.commit()
        avatar_id = av.id
    finally:
        db.close()

    db2 = client.session_factory()
    try:
        assert db2.get(Avatar, avatar_id).evolution["care"] == {"scold": 1}
    finally:
        db2.close()


def test_bump_care_flags_evolution_on_crossing(client):
    db = client.session_factory()
    try:
        av = _avatar(db)
        flags = [evolution_service.bump_care(db, av, "hug", "t")[1] for _ in range(4)]
        assert flags == [False, False, False, True]  # exp 3/6/9/12 → 第 4 次破壳
    finally:
        db.close()


def test_build_view_of_a_legacy_avatar_is_an_egg(client):
    db = client.session_factory()
    try:
        av = _avatar(db)  # evolution 默认 {}
        assert evolution_service.build_view(av)["emoji"] == "🥚"
    finally:
        db.close()
