from tests.conftest import auth_headers


def _create(client, headers):
    return client.post("/couples", headers=headers)


def test_create_returns_pending_and_pair_code(client):
    h = auth_headers(client, "alice")
    r = _create(client, h)
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "pending"
    assert body["pair_code"]


def test_join_activates_and_bootstraps(client):
    ha = auth_headers(client, "alice")
    code = _create(client, ha).json()["pair_code"]
    hb = auth_headers(client, "bob")
    r = client.post("/couples/join", headers=hb, json={"pair_code": code})
    assert r.status_code == 200
    assert r.json()["status"] == "active"

    # both partners now see an active couple
    me_a = client.get("/couples/me", headers=ha).json()
    me_b = client.get("/couples/me", headers=hb).json()
    assert me_a["status"] == "active"
    assert me_b["status"] == "active"
    assert me_a["couple_id"] == me_b["couple_id"]


def test_join_invalid_code(client):
    hb = auth_headers(client, "bob")
    r = client.post("/couples/join", headers=hb, json={"pair_code": "ZZZZZZ"})
    assert r.status_code == 404


def test_cannot_join_own_code(client):
    ha = auth_headers(client, "alice")
    code = _create(client, ha).json()["pair_code"]
    r = client.post("/couples/join", headers=ha, json={"pair_code": code})
    assert r.status_code == 400


def test_cannot_double_pair(client):
    ha = auth_headers(client, "alice")
    code = _create(client, ha).json()["pair_code"]
    hb = auth_headers(client, "bob")
    client.post("/couples/join", headers=hb, json={"pair_code": code})
    hc = auth_headers(client, "carol")
    r = client.post("/couples/join", headers=hc, json={"pair_code": code})
    assert r.status_code == 409  # already active


def test_creating_when_already_active_rejected(client):
    ha = auth_headers(client, "alice")
    code = _create(client, ha).json()["pair_code"]
    hb = auth_headers(client, "bob")
    client.post("/couples/join", headers=hb, json={"pair_code": code})
    r = _create(client, ha)
    assert r.status_code == 409


def test_me_when_unpaired(client):
    h = auth_headers(client, "solo")
    r = client.get("/couples/me", headers=h)
    assert r.status_code == 200
    assert r.json()["status"] == "none"
