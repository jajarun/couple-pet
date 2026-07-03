from tests.conftest import auth_headers


def _pair(client):
    ha = auth_headers(client, "alice")
    code = client.post("/couples", headers=ha).json()["pair_code"]
    hb = auth_headers(client, "bob")
    client.post("/couples/join", headers=hb, json={"pair_code": code})
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
