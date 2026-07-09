from tests.conftest import auth_headers, enable_ai_reply


def _pair(client):
    ha = auth_headers(client, "alice")
    code = client.post("/couples", headers=ha).json()["pair_code"]
    hb = auth_headers(client, "bob")
    client.post("/couples/join", headers=hb, json={"pair_code": code})
    # 分身回复默认关闭；这里要的是「每个动作各带一条 ai_reaction」的事件流
    enable_ai_reply(client, ha)
    enable_ai_reply(client, hb)
    return ha, hb


def _scold(client, headers, key):
    return client.post(
        "/actions",
        headers=headers,
        json={"action_type": "scold", "content": "x", "client_key": key},
    ).json()


def test_feed_is_shared_and_cursor_advances(client):
    ha, hb = _pair(client)
    _scold(client, hb, "k1")

    # alice (partner) polls from 0 and sees bob's action + ai_reaction
    full = client.get("/events?since=0", headers=ha).json()
    assert len(full["events"]) == 2
    last_id = full["events"][-1]["id"]

    # nothing new since the last id
    empty = client.get(f"/events?since={last_id}", headers=ha).json()
    assert empty["events"] == []

    # a new action shows up only above the cursor
    _scold(client, hb, "k2")
    delta = client.get(f"/events?since={last_id}", headers=ha).json()
    assert all(e["id"] > last_id for e in delta["events"])
    assert len(delta["events"]) == 2


def test_feed_includes_stats(client):
    ha, hb = _pair(client)
    _scold(client, hb, "k1")
    feed = client.get("/events?since=0", headers=hb).json()
    assert feed["stats"]["grievance"] == 15


def test_feed_requires_active_couple(client):
    h = auth_headers(client, "solo")
    assert client.get("/events?since=0", headers=h).status_code == 409


def test_feed_windowed_initial_and_older_pagination(client):
    ha, hb = _pair(client)
    for i in range(5):
        _scold(client, hb, f"k{i}")  # 5 actions × (action + ai_reaction) = 10 events, ids 1..10

    # 首屏只拿最新 4 条（升序），且提示还有更早的
    win = client.get("/events?limit=4", headers=ha).json()
    ids = [e["id"] for e in win["events"]]
    assert ids == sorted(ids) and len(ids) == 4
    assert ids == [7, 8, 9, 10]
    assert win["has_more"] is True

    # 上翻一页：更早的 4 条，全部 id 更小、仍升序
    older = client.get("/events?before=7&limit=4", headers=ha).json()
    assert [e["id"] for e in older["events"]] == [3, 4, 5, 6]
    assert older["has_more"] is True

    # 翻到底：只剩 2 条，has_more 变 False
    last = client.get("/events?before=3&limit=4", headers=ha).json()
    assert [e["id"] for e in last["events"]] == [1, 2]
    assert last["has_more"] is False


def test_feed_scoped_to_own_couple(client):
    ha, hb = _pair(client)
    _scold(client, hb, "k1")
    # a second, unrelated couple
    hc = auth_headers(client, "carol")
    code = client.post("/couples", headers=hc).json()["pair_code"]
    hd = auth_headers(client, "dave")
    client.post("/couples/join", headers=hd, json={"pair_code": code})
    feed = client.get("/events?since=0", headers=hc).json()
    assert feed["events"] == []  # carol sees nothing from alice+bob
