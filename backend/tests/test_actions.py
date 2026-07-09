from app.rules.actions import LOCAL_REACTIONS
from tests.conftest import auth_headers, enable_ai_reply


def _pair(client, ai_reply=True):
    ha = auth_headers(client, "alice")
    code = client.post("/couples", headers=ha).json()["pair_code"]
    hb = auth_headers(client, "bob")
    client.post("/couples/join", headers=hb, json={"pair_code": code})
    # alice sets her persona so the stub reaction is in-persona
    client.put("/avatars/mine", headers=ha, json={"persona": {"tone": "毒舌"}})
    if ai_reply:  # 分身回复默认关闭，这批用例要的是「分身接话」的行为
        enable_ai_reply(client, ha)
        enable_ai_reply(client, hb)
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


def test_reply_disabled_by_default_produces_no_ai_reaction(client):
    ha, hb = _pair(client, ai_reply=False)
    r = _act(client, hb, "scold", "k1", "大猪蹄子")
    assert r.status_code == 200
    body = r.json()
    kinds = [e["kind"] for e in body["events"]]
    assert kinds == ["action"]  # 分身彻底不接话
    assert body["stats"]["grievance"] == 15  # 数值照常结算


def test_enabling_reply_brings_the_avatar_back(client):
    ha, hb = _pair(client, ai_reply=False)
    assert [e["kind"] for e in _act(client, hb, "poke", "k1").json()["events"]] == ["action"]
    enable_ai_reply(client, hb)
    kinds = [e["kind"] for e in _act(client, hb, "poke", "k2").json()["events"]]
    assert "ai_reaction" in kinds


def test_disabled_reply_burns_no_ai_quota(client, monkeypatch):
    ha, hb = _pair(client, ai_reply=False)
    import app.routers.actions as m

    calls = []
    monkeypatch.setattr(m, "ai_quota_available", lambda user, db: calls.append("check") or True)
    monkeypatch.setattr(m, "record_ai_usage", lambda user, db: calls.append("charge"))
    _act(client, hb, "scold", "k1", "大猪蹄子")  # scold 本是 AI 动作
    assert calls == []  # 关掉后连额度都不查，更不会扣


def test_switch_is_per_keeper(client):
    """决策 3：开关管「我养的那只分身」，各管各的观看体验。"""
    ha, hb = _pair(client, ai_reply=False)
    enable_ai_reply(client, hb)  # 只有 bob 开
    bob_kinds = [e["kind"] for e in _act(client, hb, "poke", "kb").json()["events"]]
    alice_kinds = [e["kind"] for e in _act(client, ha, "poke", "ka").json()["events"]]
    assert "ai_reaction" in bob_kinds
    assert "ai_reaction" not in alice_kinds


def test_local_reactions_are_plentiful_and_unique():
    for action, lines in LOCAL_REACTIONS.items():
        assert len(lines) >= 50, f"{action} only has {len(lines)} lines"
        assert len(set(lines)) == len(lines), f"{action} has duplicate lines"


def test_bundle_carries_the_evolution_view(client):
    ha, hb = _pair(client)
    body = _act(client, hb, "poke", "k1").json()
    assert body["evolved"] is False
    assert body["evolution"]["stage"] == 0
    assert body["evolution"]["exp"] == 1
    assert body["evolution"]["emoji"] == "🥚"


def test_crossing_a_stage_flags_evolved_and_drops_a_standalone_system_event(client):
    ha, hb = _pair(client)
    for i in range(3):  # hug=3 exp/次
        assert _act(client, hb, "hug", f"h{i}").json()["evolved"] is False
    body = _act(client, hb, "hug", "h3").json()  # exp 12 → 破壳
    assert body["evolved"] is True
    assert body["evolution"]["stage"] == 1

    # 庆祝事件不挂 parent，所以不在 bundle 里——否则会跟「委屈爆表」旁白抢 comfortText
    assert [e["kind"] for e in body["events"]] == ["action", "ai_reaction"]
    feed = client.get("/events", headers=hb).json()["events"]
    evolved_events = [e for e in feed if e["action_type"] == "evolve"]
    assert len(evolved_events) == 1
    assert evolved_events[0]["kind"] == "system"
    assert evolved_events[0]["parent_event_id"] is None


def test_idempotent_replay_does_not_grow_experience(client):
    ha, hb = _pair(client)
    first = _act(client, hb, "hug", "same").json()
    second = _act(client, hb, "hug", "same").json()
    assert first["evolution"]["exp"] == second["evolution"]["exp"] == 3
    assert second["evolved"] is False


def test_each_keeper_grows_their_own_avatar(client):
    """镜像分身各长各的：进化只由「饲养者对这只分身做了什么」推动，不吃 couple 级共享数值。"""
    ha, hb = _pair(client)
    for i in range(4):
        _act(client, hb, "hug", f"b{i}")  # bob 猛抱他养的那只（代表 alice）
    _act(client, ha, "poke", "a0")        # alice 只戳了一下她养的那只（代表 bob）
    assert client.get("/avatars/pet", headers=hb).json()["evolution"]["exp"] == 12
    assert client.get("/avatars/pet", headers=ha).json()["evolution"]["exp"] == 1


def test_adult_branch_reaches_the_ai_persona(client, monkeypatch):
    """闭环：养歪了的形态反过来改写分身的说话方式。"""
    ha, hb = _pair(client)
    # 先抱一下：1 小时窗口里有过安抚就不会出走，否则骂到第 5 次分身就跑了（rules/runaway.py）
    _act(client, hb, "hug", "h0", "")
    for i in range(40):  # scold=1 exp/次 → exp 40+ → 成体，几乎全是骂 → dark
        _act(client, hb, "scold", f"s{i}", "菜")
    import app.routers.actions as m

    seen = {}
    monkeypatch.setattr(m, "generate_reaction", lambda persona, *a, **k: (seen.update(persona) or ("ok", False)))
    _act(client, hb, "chat", "c1", "在吗")
    assert seen["branch"] == "dark"


def test_branch_stays_empty_before_adulthood(client, monkeypatch):
    ha, hb = _pair(client)
    import app.routers.actions as m

    seen = {}
    monkeypatch.setattr(m, "generate_reaction", lambda persona, *a, **k: (seen.update(persona) or ("ok", False)))
    _act(client, hb, "chat", "c1", "在吗")
    assert seen["branch"] == ""  # 没定型就别让 prompt 提前剧透形态
