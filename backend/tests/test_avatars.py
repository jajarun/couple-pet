from tests.conftest import auth_headers


def _pair(client):
    ha = auth_headers(client, "alice")
    code = client.post("/couples", headers=ha).json()["pair_code"]
    hb = auth_headers(client, "bob")
    client.post("/couples/join", headers=hb, json={"pair_code": code})
    return ha, hb


def test_edit_mine_and_partner_sees_it_as_pet(client):
    ha, hb = _pair(client)
    r = client.put(
        "/avatars/mine",
        headers=ha,
        json={"name": "狗蛋", "appearance": {"emoji": "🐶"}, "persona": {"tone": ["毒舌", "傲娇"]}},
    )
    assert r.status_code == 200
    assert r.json()["name"] == "狗蛋"

    # bob keeps alice's avatar as his pet
    pet = client.get("/avatars/pet", headers=hb).json()
    assert pet["name"] == "狗蛋"
    assert pet["persona"] == {"tone": ["毒舌", "傲娇"]}
    assert pet["subject_user_id"] != pet["keeper_user_id"]


def test_mine_is_the_one_i_am_subject_of(client):
    ha, hb = _pair(client)
    mine = client.get("/avatars/mine", headers=ha).json()
    pet = client.get("/avatars/pet", headers=ha).json()
    assert mine["id"] != pet["id"]
    assert mine["subject_user_id"] == pet["keeper_user_id"]  # both are alice's id


def test_requires_active_couple(client):
    h = auth_headers(client, "solo")
    assert client.get("/avatars/mine", headers=h).status_code == 409
    assert client.put("/avatars/mine", headers=h, json={"name": "x"}).status_code == 409


def test_both_endpoints_expose_the_evolution_view(client):
    ha, hb = _pair(client)
    # /pet = 我把 TA 养成了什么样；/mine = 我在 TA 眼里被养成了什么样。刚配对都是一颗蛋。
    for path in ("/avatars/pet", "/avatars/mine"):
        evo = client.get(path, headers=ha).json()["evolution"]
        assert evo["stage"] == 0 and evo["exp"] == 0
        assert evo["emoji"] == "🥚" and evo["use_form_emoji"] is False
        assert evo["next_exp"] == 10


def test_mine_reflects_how_my_partner_treats_me(client):
    """核心情感设计：我在「我」页签看到的，是 TA 养的那只——TA 怎么对我的，一目了然。"""
    ha, hb = _pair(client)
    for i in range(4):  # bob 猛抱他养的那只（代表 alice）
        client.post(
            "/actions", headers=hb, json={"action_type": "hug", "content": "", "client_key": f"b{i}"}
        )
    assert client.get("/avatars/mine", headers=ha).json()["evolution"]["exp"] == 12
    assert client.get("/avatars/mine", headers=hb).json()["evolution"]["exp"] == 0
