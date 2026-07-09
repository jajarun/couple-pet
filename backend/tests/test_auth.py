from tests.conftest import auth_headers, register


def test_register_returns_token_and_user(client):
    r = register(client, "alice")
    assert r.status_code == 200
    body = r.json()
    assert body["access_token"]
    assert body["user"]["nickname"] == "alice"
    assert "password" not in body["user"]


def test_duplicate_nickname_rejected(client):
    register(client, "alice")
    r = register(client, "alice")
    assert r.status_code == 409


def test_login_success_and_wrong_password(client):
    register(client, "bob", "secret1")
    ok = client.post("/auth/login", json={"nickname": "bob", "password": "secret1"})
    assert ok.status_code == 200
    assert ok.json()["access_token"]
    bad = client.post("/auth/login", json={"nickname": "bob", "password": "nope"})
    assert bad.status_code == 401


def test_login_unknown_user(client):
    r = client.post("/auth/login", json={"nickname": "ghost", "password": "x"})
    assert r.status_code == 401


def test_ai_reply_is_off_by_default(client):
    h = auth_headers(client, "alice")
    assert client.get("/auth/me", headers=h).json()["ai_reply_enabled"] is False
    # 登录/注册响应里也带着，前端不用额外拉一次
    assert register(client, "bob").json()["user"]["ai_reply_enabled"] is False


def test_patch_me_toggles_ai_reply(client):
    h = auth_headers(client, "alice")
    r = client.patch("/auth/me", headers=h, json={"ai_reply_enabled": True})
    assert r.status_code == 200 and r.json()["ai_reply_enabled"] is True
    assert client.get("/auth/me", headers=h).json()["ai_reply_enabled"] is True  # 落库了
    r = client.patch("/auth/me", headers=h, json={"ai_reply_enabled": False})
    assert r.json()["ai_reply_enabled"] is False


def test_patch_me_omitting_a_field_leaves_it_alone(client):
    h = auth_headers(client, "alice")
    client.patch("/auth/me", headers=h, json={"ai_reply_enabled": True})
    r = client.patch("/auth/me", headers=h, json={})  # PATCH 语义：没给就别动
    assert r.json()["ai_reply_enabled"] is True


def test_me_requires_auth(client):
    assert client.get("/auth/me").status_code == 401
