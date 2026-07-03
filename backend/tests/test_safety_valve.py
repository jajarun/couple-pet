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


def test_system_narration_appears_when_grievance_maxes(client):
    ha, hb = _pair(client)
    bundle = {}
    # scold +15 each; 6 scolds → 90 >= threshold 80 (fast, minimal time decay)
    for i in range(6):
        bundle = _scold(client, hb, f"k{i}")
    kinds = [e["kind"] for e in bundle["events"]]
    assert "system" in kinds
    system_ev = next(e for e in bundle["events"] if e["kind"] == "system")
    assert system_ev["content"]  # a comfort nudge, not empty
    assert system_ev["parent_event_id"] is not None


def test_no_system_narration_below_threshold(client):
    ha, hb = _pair(client)
    bundle = _scold(client, hb, "k0")  # grievance 15, well below 80
    kinds = [e["kind"] for e in bundle["events"]]
    assert "system" not in kinds
