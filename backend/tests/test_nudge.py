from app.rules.actions import NUDGE_LINES
from tests.conftest import auth_headers


def _pair_ready(client):
    """Pair alice+bob and give alice's avatar a name so bob's pet is 'captured'."""
    ha = auth_headers(client, "alice")
    code = client.post("/couples", headers=ha).json()["pair_code"]
    hb = auth_headers(client, "bob")
    client.post("/couples/join", headers=hb, json={"pair_code": code})
    client.put("/avatars/mine", headers=ha, json={"name": "小恶魔", "persona": {"tone": "毒舌"}})
    return ha, hb


def test_nudge_fires_when_idle_then_throttles(client):
    ha, hb = _pair_ready(client)
    # no DeepSeek key in tests → local NUDGE_LINES, and the feed is empty → idle → fires
    r = client.post("/nudge", headers=hb)
    assert r.status_code == 200
    ev = r.json()["event"]
    assert ev is not None
    assert ev["kind"] == "ai_reaction"
    assert ev["action_type"] == "nudge"
    assert ev["parent_event_id"] is None
    assert ev["content"] in NUDGE_LINES
    # the nudge itself is a fresh event → an immediate re-poll is throttled
    assert client.post("/nudge", headers=hb).json()["event"] is None


def test_nudge_attributes_to_the_speaking_subject(client):
    ha, hb = _pair_ready(client)
    partner_id = client.get("/couples/me", headers=hb).json()["partner_id"]
    ev = client.post("/nudge", headers=hb).json()["event"]
    # actor = the avatar's subject (TA), so the frontend can side it left for the keeper
    assert ev["actor_user_id"] == partner_id


def test_nudge_needs_a_captured_pet(client):
    ha = auth_headers(client, "alice")
    code = client.post("/couples", headers=ha).json()["pair_code"]
    hb = auth_headers(client, "bob")
    client.post("/couples/join", headers=hb, json={"pair_code": code})
    # alice never named her avatar → bob's pet is still an egg → no nudge
    assert client.post("/nudge", headers=hb).json()["event"] is None


def test_nudge_requires_active_couple(client):
    h = auth_headers(client, "solo")
    assert client.post("/nudge", headers=h).json()["event"] is None


def test_nudge_ignores_the_ai_reply_switch(client):
    """「分身回复」默认关闭（_pair_ready 没开），主动撩人照样触发。"""
    ha, hb = _pair_ready(client)
    ev = client.post("/nudge", headers=hb).json()["event"]
    assert ev is not None and ev["action_type"] == "nudge"
