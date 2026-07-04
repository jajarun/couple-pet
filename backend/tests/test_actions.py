from app.rules.actions import LOCAL_REACTIONS
from tests.conftest import auth_headers


def _pair(client):
    ha = auth_headers(client, "alice")
    code = client.post("/couples", headers=ha).json()["pair_code"]
    hb = auth_headers(client, "bob")
    client.post("/couples/join", headers=hb, json={"pair_code": code})
    # alice sets her persona so the stub reaction is in-persona
    client.put("/avatars/mine", headers=ha, json={"persona": {"tone": "毒舌"}})
    return ha, hb


def _act(client, headers, action_type, key, content=""):
    return client.post(
        "/actions",
        headers=headers,
        json={"action_type": action_type, "content": content, "client_key": key},
    )


def test_scold_produces_action_and_ai_reaction(client):
    ha, hb = _pair(client)
    # bob scolds his pet (alice's avatar, persona 毒舌)
    r = _act(client, hb, "scold", "k1", "大猪蹄子")
    assert r.status_code == 200
    body = r.json()
    kinds = [e["kind"] for e in body["events"]]
    assert "action" in kinds and "ai_reaction" in kinds
    reaction = next(e for e in body["events"] if e["kind"] == "ai_reaction")
    assert reaction["parent_event_id"] is not None
    assert "毒舌" in reaction["content"]
    assert body["stats"]["grievance"] == 15
    assert body["events"][0]["created_at"].endswith("Z")


def test_cheap_action_uses_local_template(client):
    ha, hb = _pair(client)
    r = _act(client, hb, "feed_dogfood", "k1")
    reaction = next(e for e in r.json()["events"] if e["kind"] == "ai_reaction")
    assert reaction["content"] in LOCAL_REACTIONS["feed_dogfood"]
    assert r.json()["stats"]["dogfood"] == 20


def test_idempotent_replay_returns_same_events(client):
    ha, hb = _pair(client)
    first = _act(client, hb, "scold", "same-key", "x").json()
    second = _act(client, hb, "scold", "same-key", "x").json()
    assert [e["id"] for e in first["events"]] == [e["id"] for e in second["events"]]
    # grievance did not double-apply
    assert second["stats"]["grievance"] == 15


def test_unknown_action_rejected(client):
    ha, hb = _pair(client)
    r = _act(client, hb, "nope", "k1")
    assert r.status_code == 422


def test_requires_active_couple(client):
    h = auth_headers(client, "solo")
    r = _act(client, h, "scold", "k1", "x")
    assert r.status_code == 409


def test_over_quota_falls_back_to_local(client, monkeypatch):
    ha, hb = _pair(client)
    import app.routers.actions as actions_mod

    monkeypatch.setattr(actions_mod, "ai_quota_available", lambda user, db: False)
    r = _act(client, hb, "scold", "k1", "大猪蹄子")
    assert r.status_code == 200  # never errors on quota exhaustion
    reaction = next(e for e in r.json()["events"] if e["kind"] == "ai_reaction")
    assert reaction["content"]  # a fallback line, not empty


def test_ai_success_uses_ai_text_and_charges(client, monkeypatch):
    ha, hb = _pair(client)
    import app.routers.actions as m

    charged = []
    monkeypatch.setattr(m, "generate_reaction", lambda *a, **k: ("哼，本汪偏要理你", True))
    monkeypatch.setattr(m, "record_ai_usage", lambda user, db: charged.append(1))
    r = _act(client, hb, "chat", "k1", "在吗")
    assert r.status_code == 200
    reaction = next(e for e in r.json()["events"] if e["kind"] == "ai_reaction")
    assert reaction["content"] == "哼，本汪偏要理你"
    assert charged == [1]  # 成功才扣，且只扣一次


def test_ai_failure_does_not_charge(client, monkeypatch):
    ha, hb = _pair(client)
    import app.routers.actions as m

    charged = []
    monkeypatch.setattr(m, "generate_reaction", lambda *a, **k: ("（分身充电中）", False))
    monkeypatch.setattr(m, "record_ai_usage", lambda user, db: charged.append(1))
    r = _act(client, hb, "chat", "k1", "在吗")
    assert r.status_code == 200
    reaction = next(e for e in r.json()["events"] if e["kind"] == "ai_reaction")
    assert reaction["content"] == "（分身充电中）"
    assert charged == []  # 失败不烧额度
    assert r.json()["stats"]  # 动作照样成立、数值已结算


def test_recent_context_is_thread_scoped(client, monkeypatch):
    ha, hb = _pair(client)
    _act(client, ha, "chat", "a1", "ALICE_ONLY")   # alice's own thread
    _act(client, hb, "chat", "b1", "BOB_FIRST")    # bob's prior thread
    import app.routers.actions as m

    captured = {}

    def fake_gen(persona, stats, action_type, content, recent, memory_summary=""):
        captured["recent"] = recent
        return ("ok", False)

    monkeypatch.setattr(m, "generate_reaction", fake_gen)
    _act(client, hb, "chat", "b2", "BOB_SECOND")
    joined = " ".join(t["text"] for t in captured["recent"])
    assert "BOB_FIRST" in joined       # bob's own prior turn is present
    assert "ALICE_ONLY" not in joined  # the other avatar's thread must NOT leak in


def test_content_length_capped(client):
    ha, hb = _pair(client)
    r = _act(client, hb, "chat", "k1", "x" * 1001)
    assert r.status_code == 422
