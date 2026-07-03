from tests.conftest import register


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
