from tests.conftest import auth_headers


def _pair(client):
    ha = auth_headers(client, "alice")
    code = client.post("/couples", headers=ha).json()["pair_code"]
    hb = auth_headers(client, "bob")
    client.post("/couples/join", headers=hb, json={"pair_code": code})
    return ha, hb


def _scold(client, headers, key="k1"):
    return client.post(
        "/actions",
        headers=headers,
        json={"action_type": "scold", "content": "大猪蹄子", "client_key": key},
    ).json()


def test_subject_can_respond_to_partner_action(client):
    ha, hb = _pair(client)
    bundle = _scold(client, hb)  # bob acts on alice's avatar; alice is the subject
    action_id = next(e["id"] for e in bundle["events"] if e["kind"] == "action")
    r = client.post(
        f"/events/{action_id}/respond",
        headers=ha,
        json={"content": "你才是猪蹄子", "client_key": "resp1"},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["kind"] == "real_response"
    assert body["parent_event_id"] == action_id


def test_actor_cannot_respond_to_own_action(client):
    ha, hb = _pair(client)
    bundle = _scold(client, hb)
    action_id = next(e["id"] for e in bundle["events"] if e["kind"] == "action")
    r = client.post(
        f"/events/{action_id}/respond",
        headers=hb,  # bob was the actor
        json={"content": "自问自答", "client_key": "resp1"},
    )
    assert r.status_code == 403


def test_cannot_respond_to_event_in_other_couple(client):
    ha, hb = _pair(client)
    bundle = _scold(client, hb)
    action_id = next(e["id"] for e in bundle["events"] if e["kind"] == "action")
    outsider = auth_headers(client, "carol")
    r = client.post(
        f"/events/{action_id}/respond",
        headers=outsider,
        json={"content": "路过", "client_key": "resp1"},
    )
    assert r.status_code in (403, 404)


def test_respond_client_key_may_collide_with_an_action_key(client):
    ha, hb = _pair(client)
    bundle = _scold(client, hb, key="k1")  # action uses client_key "k1"
    action_id = next(e["id"] for e in bundle["events"] if e["kind"] == "action")
    r = client.post(
        f"/events/{action_id}/respond",
        headers=ha,
        json={"content": "x", "client_key": "k1"},  # reuse the action's key
    )
    assert r.status_code == 200          # was 500 before the constraint fix
    assert r.json()["kind"] == "real_response"


def test_respond_is_idempotent(client):
    ha, hb = _pair(client)
    bundle = _scold(client, hb)
    action_id = next(e["id"] for e in bundle["events"] if e["kind"] == "action")
    first = client.post(
        f"/events/{action_id}/respond", headers=ha,
        json={"content": "x", "client_key": "resp1"},
    ).json()
    second = client.post(
        f"/events/{action_id}/respond", headers=ha,
        json={"content": "x", "client_key": "resp1"},
    ).json()
    assert first["id"] == second["id"]
