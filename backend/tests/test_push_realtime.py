"""实时推送挂点：借 TestClient 会同步跑完 BackgroundTasks 的特性，
monkeypatch push_service.send_to_user 记录调用，断言「发给对方、不发给自己」。"""

import app.push_service as ps
from tests.conftest import auth_headers


def _pair(client):
    ha = auth_headers(client, "alice")  # 注册顺序 → alice=user 1
    code = client.post("/couples", headers=ha).json()["pair_code"]
    hb = auth_headers(client, "bob")  # bob=user 2
    client.post("/couples/join", headers=hb, json={"pair_code": code})
    return ha, hb


def test_action_pushes_to_partner_not_self(client, monkeypatch):
    calls = []
    monkeypatch.setattr(ps, "send_to_user", lambda uid, p: calls.append((uid, p)))
    ha, _ = _pair(client)
    client.post("/actions", headers=ha, json={"action_type": "poke", "content": "", "client_key": "p1"})
    assert len(calls) == 1
    assert calls[0][0] == 2  # 发给对方 bob，不发给自己 alice
    assert calls[0][1]["tag"] == "action"


def test_duplicate_action_does_not_repush(client, monkeypatch):
    calls = []
    monkeypatch.setattr(ps, "send_to_user", lambda uid, p: calls.append((uid, p)))
    ha, _ = _pair(client)
    body = {"action_type": "poke", "content": "", "client_key": "same"}
    client.post("/actions", headers=ha, json=body)
    client.post("/actions", headers=ha, json=body)  # 幂等重放
    assert len(calls) == 1  # 只推一次


def test_comfort_push_when_grievance_explodes(client, monkeypatch):
    calls = []
    monkeypatch.setattr(ps, "send_to_user", lambda uid, p: calls.append((uid, p)))
    ha, _ = _pair(client)
    # 先抱一下：1 小时窗口里有过安抚就不会出走，否则骂到第 5 次分身就跑了（rules/runaway.py）
    client.post("/actions", headers=ha, json={"action_type": "hug", "content": "", "client_key": "h0"})
    # 连续骂到委屈爆表（scold +15/次），最后一条应发「委屈」而非「action」
    for i in range(8):
        client.post("/actions", headers=ha, json={"action_type": "scold", "content": "", "client_key": f"s{i}"})
    assert calls[-1][1]["tag"] == "comfort"


def test_daily_first_answer_pushes_partner(client, monkeypatch):
    calls = []
    monkeypatch.setattr(ps, "send_to_user", lambda uid, p: calls.append((uid, p)))
    ha, hb = _pair(client)
    client.get("/daily", headers=ha)
    client.post("/daily/answer", headers=ha, json={"content": "A", "client_key": "a1"})
    assert len(calls) == 1
    assert calls[0][0] == 2 and calls[0][1]["tag"] == "daily"  # 催对方 bob 来答
    calls.clear()
    client.post("/daily/answer", headers=hb, json={"content": "B", "client_key": "b1"})
    assert calls == []  # 第二个答的人不再催


def test_respond_pushes_to_original_actor(client, monkeypatch):
    calls = []
    ha, hb = _pair(client)
    # bob 先发一个动作，产生一条 action 事件
    r = client.post("/actions", headers=hb, json={"action_type": "poke", "content": "", "client_key": "b0"})
    action_id = r.json()["events"][0]["id"]
    # 之后再挂记录器：alice 本尊回应 bob 那条动作 → 应推给发起者 bob(2)
    monkeypatch.setattr(ps, "send_to_user", lambda uid, p: calls.append((uid, p)))
    client.post(f"/events/{action_id}/respond", headers=ha, json={"content": "本尊回你", "client_key": "r1"})
    assert len(calls) == 1
    assert calls[0][0] == 2 and calls[0][1]["tag"] == "respond"
