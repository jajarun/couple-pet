from sqlalchemy.exc import IntegrityError

import app.routers.daily as daily_module
from tests.conftest import auth_headers


def _pair(client):
    ha = auth_headers(client, "alice")
    code = client.post("/couples", headers=ha).json()["pair_code"]
    hb = auth_headers(client, "bob")
    client.post("/couples/join", headers=hb, json={"pair_code": code})
    return ha, hb


def test_get_daily_generates_question_and_streak(client):
    ha, hb = _pair(client)
    r = client.get("/daily", headers=ha)
    assert r.status_code == 200
    body = r.json()
    assert body["question"]["text"]                 # 有题
    assert body["question"]["flavor"] in ("ambiguous", "deep", "silly")
    assert body["my_answer"] is None
    assert body["both_answered"] is False
    assert body["streak"]["count"] == 0
    assert body["streak"]["rescuable"] is False       # 火苗没断，不给续


def test_get_daily_uses_ai_question_when_key_present(client, monkeypatch):
    # 有 key 时,当天首拉 /daily 用 AI 出题(不占个人额度);双方随后看到同一道 AI 题
    from app.config import settings

    monkeypatch.setattr(settings, "deepseek_api_key", "sk-test")
    monkeypatch.setattr("app.ai.daily_question.chat_completion", lambda messages: "AI 给你俩出的题?")
    ha, hb = _pair(client)
    a = client.get("/daily", headers=ha).json()
    assert a["question"]["text"] == "AI 给你俩出的题?"
    b = client.get("/daily", headers=hb).json()
    assert b["question"]["text"] == "AI 给你俩出的题?"   # 记库后双方一致


def test_get_daily_falls_back_to_local_without_key(client, monkeypatch):
    # 无 key(默认)时回落本地题库,离线照常出题
    from app.config import settings
    from app.rules import daily_questions

    monkeypatch.setattr(settings, "deepseek_api_key", "")
    ha, hb = _pair(client)
    body = client.get("/daily", headers=ha).json()
    flavor = body["question"]["flavor"]
    assert body["question"]["text"] in daily_questions.LOCAL_QUESTIONS[flavor]


def test_get_daily_is_stable_same_day(client):
    ha, hb = _pair(client)
    q1 = client.get("/daily", headers=ha).json()["question"]["text"]
    q2 = client.get("/daily", headers=hb).json()["question"]["text"]  # 同一对、同一天
    assert q1 == q2                                  # 双方看到同一道题、且不变


def test_answer_waits_until_both_then_unlocks(client):
    ha, hb = _pair(client)
    client.get("/daily", headers=ha)                 # 生成题
    # alice 先答
    ra = client.post("/daily/answer", headers=ha, json={"content": "爱丽丝的答案", "client_key": "a1"})
    assert ra.status_code == 200
    a_body = ra.json()
    assert a_body["my_answer"] == "爱丽丝的答案"
    assert a_body["both_answered"] is False
    assert a_body["partner_answer"] is None          # 对方还没答，看不到
    # bob 后答 → 解锁
    rb = client.post("/daily/answer", headers=hb, json={"content": "鲍勃的答案", "client_key": "b1"})
    b_body = rb.json()
    assert b_body["both_answered"] is True
    assert b_body["my_answer"] == "鲍勃的答案"
    assert b_body["partner_answer"] == "爱丽丝的答案"  # 解锁后能看到对方
    # alice 再拉，也解锁了
    a2 = client.get("/daily", headers=ha).json()
    assert a2["both_answered"] is True
    assert a2["partner_answer"] == "鲍勃的答案"


def test_answer_is_idempotent(client):
    ha, hb = _pair(client)
    client.get("/daily", headers=ha)
    first = client.post("/daily/answer", headers=ha, json={"content": "答案一", "client_key": "a1"}).json()
    again = client.post("/daily/answer", headers=ha, json={"content": "答案二", "client_key": "a1"}).json()
    assert again["my_answer"] == "答案一"            # 首答锁定，不被覆盖


def test_reveal_drops_daily_qa_event_into_timeline(client):
    ha, hb = _pair(client)
    client.get("/daily", headers=ha)
    client.post("/daily/answer", headers=ha, json={"content": "AAA", "client_key": "a1"})
    client.post("/daily/answer", headers=hb, json={"content": "BBB", "client_key": "b1"})
    feed = client.get("/events", headers=ha).json()
    qa = [e for e in feed["events"] if e["kind"] == "daily_qa"]
    assert len(qa) == 3                              # 1 父题 + 2 答
    parent = next(e for e in qa if e["parent_event_id"] is None)
    answers = [e for e in qa if e["parent_event_id"] == parent["id"]]
    assert {e["content"] for e in answers} == {"AAA", "BBB"}


def test_answering_counts_toward_streak(client):
    ha, hb = _pair(client)
    client.get("/daily", headers=ha)
    client.post("/daily/answer", headers=ha, json={"content": "x", "client_key": "a1"})
    client.post("/daily/answer", headers=hb, json={"content": "y", "client_key": "b1"})
    body = client.get("/daily", headers=ha).json()
    assert body["streak"]["count"] == 1             # 两人都答了 → 火苗起


def test_actions_also_bump_streak(client):
    # 用互动动作（非答题）端到端验证 Task 4 在 /actions 里接的 do_touch
    ha, hb = _pair(client)
    client.post("/actions", headers=ha, json={"action_type": "poke", "content": "", "client_key": "pa"})
    client.post("/actions", headers=hb, json={"action_type": "poke", "content": "", "client_key": "pb"})
    body = client.get("/daily", headers=ha).json()
    assert body["streak"]["count"] == 1


def test_requires_active_couple(client):
    h = auth_headers(client, "solo")
    assert client.get("/daily", headers=h).status_code == 409


def test_get_daily_recovers_from_concurrent_insert_conflict(client, monkeypatch):
    # 模拟双方几乎同时首次拉题：第一次撞唯一约束抛 IntegrityError，
    # 路由应 rollback 后重试一次并成功返回 200，而不是让 500 冒出去。
    ha, hb = _pair(client)

    real_get_or_create_question = daily_module._get_or_create_question
    calls = {"n": 0}

    def flaky_get_or_create_question(db, couple):
        calls["n"] += 1
        if calls["n"] == 1:
            raise IntegrityError("stmt", {}, Exception("orig"))
        return real_get_or_create_question(db, couple)

    monkeypatch.setattr(daily_module, "_get_or_create_question", flaky_get_or_create_question)

    r = client.get("/daily", headers=ha)
    assert r.status_code == 200                     # 没有 500 冒出去
    body = r.json()
    assert body["question"]["text"]                 # 重试后正常拿到题
    assert calls["n"] == 2                           # 确实撞车了一次、重试了一次


def test_rescue_rejected_when_not_broken(client):
    ha, hb = _pair(client)
    client.get("/daily", headers=ha)
    r = client.post("/streak/rescue", headers=ha)
    assert r.status_code == 409          # 火苗没断，没得救


def test_rescue_restores_streak_and_costs_intimacy(client, monkeypatch):
    # 端到端:前天两人 hug 起火 → 跳过昨天(漏正好一天)→ 火苗可救 → 续火恢复天数、扣 5 亲密
    import app.streak_service as ss
    from datetime import date

    ha, hb = _pair(client)
    day = {"d": date(2026, 7, 6)}                      # 前天
    monkeypatch.setattr(ss, "_today", lambda: day["d"])
    client.post("/actions", headers=ha, json={"action_type": "hug", "content": "", "client_key": "h1"})
    client.post("/actions", headers=hb, json={"action_type": "hug", "content": "", "client_key": "h2"})
    assert client.get("/daily", headers=ha).json()["streak"]["count"] == 1

    day["d"] = date(2026, 7, 8)                        # 跳过昨天 → 漏正好一天
    v = client.get("/daily", headers=ha).json()["streak"]
    assert v["count"] == 0                             # 断了显示 0
    assert v["rescuable"] is True                      # 但可救 → 露出续火按钮

    before = client.get("/events", headers=ha).json()["stats"]["intimacy"]
    r = client.post("/streak/rescue", headers=ha)
    assert r.status_code == 200
    assert r.json()["count"] == 1                      # 天数恢复
    assert r.json()["rescuable"] is False              # 救过就不再可救
    after = client.get("/events", headers=ha).json()["stats"]["intimacy"]
    assert after == before - 5                         # 花了 5 亲密


def test_answer_rejects_empty_content(client):
    ha, hb = _pair(client)
    client.get("/daily", headers=ha)                 # 生成题
    r = client.post("/daily/answer", headers=ha, json={"content": "", "client_key": "x"})
    assert r.status_code == 422                       # 空答案不许解锁


def test_answer_recovers_from_concurrent_insert_conflict(client, monkeypatch):
    # 和 GET 那条一样的道理，只是发生在答题这条路上：两边几乎同时首次拉题触发的插入
    # 冲突，也可能撞到答题接口自己身上。回答请求内部第一次遇到 IntegrityError 时，
    # 路由应 rollback 后重试一次并成功返回 200，而不是让 500 冒出去。
    ha, hb = _pair(client)
    client.get("/daily", headers=ha)                 # 先把题生成好，别和取题自身的重试路径搅在一起

    real_get_or_create_question = daily_module._get_or_create_question
    calls = {"n": 0}

    def flaky_get_or_create_question(db, couple):
        calls["n"] += 1
        if calls["n"] == 1:
            raise IntegrityError("stmt", {}, Exception("orig"))
        return real_get_or_create_question(db, couple)

    monkeypatch.setattr(daily_module, "_get_or_create_question", flaky_get_or_create_question)

    r = client.post("/daily/answer", headers=ha, json={"content": "答案", "client_key": "a1"})
    assert r.status_code == 200                       # 没有 500 冒出去
    body = r.json()
    assert body["my_answer"] == "答案"                 # 重试后答案确实写进去了
    assert calls["n"] == 2                             # 确实撞车了一次、重试了一次
