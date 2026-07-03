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
        json={"name": "狗蛋", "appearance": {"emoji": "🐶"}, "persona": {"tone": "毒舌"}},
    )
    assert r.status_code == 200
    assert r.json()["name"] == "狗蛋"

    # bob keeps alice's avatar as his pet
    pet = client.get("/avatars/pet", headers=hb).json()
    assert pet["name"] == "狗蛋"
    assert pet["persona"] == {"tone": "毒舌"}
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
