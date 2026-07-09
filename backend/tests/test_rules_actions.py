import pytest

from app.rules.actions import ACTION_TYPES, AI_ACTIONS, LOCAL_REACTIONS, apply_action


def test_action_types_cover_roast_and_sweet():
    assert set(ACTION_TYPES) == {
        "scold", "poke", "feed_dogfood", "hug", "miss_you", "apologize", "chat", "coax"
    }
    assert AI_ACTIONS == {"scold", "chat"}


def test_coax_soothes_and_warms():
    stats = {"grievance": 90, "dogfood": 0, "miss": 0, "intimacy": 10}
    new, needs_ai, reaction = apply_action(stats, "coax")
    assert new["grievance"] == 60   # -30
    assert new["intimacy"] == 15    # +5
    assert needs_ai is False
    assert reaction in LOCAL_REACTIONS["coax"]


def test_scold_raises_grievance_and_flags_ai():
    stats = {"grievance": 10, "dogfood": 0, "miss": 0, "intimacy": 0}
    new, needs_ai, reaction = apply_action(stats, "scold")
    assert new["grievance"] == 25   # +15
    assert needs_ai is True
    assert reaction is None


def test_feed_dogfood_local_reaction_and_stat_moves():
    stats = {"grievance": 30, "dogfood": 0, "miss": 0, "intimacy": 0}
    new, needs_ai, reaction = apply_action(stats, "feed_dogfood")
    assert new["dogfood"] == 20     # +20
    assert new["grievance"] == 20   # -10
    assert needs_ai is False
    assert reaction in LOCAL_REACTIONS["feed_dogfood"]


def test_hug_converts_miss_to_intimacy():
    stats = {"grievance": 0, "dogfood": 0, "miss": 40, "intimacy": 5}
    new, _, _ = apply_action(stats, "hug")
    assert new["miss"] == 10        # -30
    assert new["intimacy"] == 15    # +10


def test_apologize_lowers_grievance_raises_intimacy():
    stats = {"grievance": 50, "dogfood": 0, "miss": 0, "intimacy": 0}
    new, _, _ = apply_action(stats, "apologize")
    assert new["grievance"] == 25   # -25
    assert new["intimacy"] == 8     # +8


def test_chat_is_ai_no_stat_change():
    stats = {"grievance": 10, "dogfood": 10, "miss": 10, "intimacy": 10}
    new, needs_ai, reaction = apply_action(stats, "chat")
    assert new == stats
    assert needs_ai is True
    assert reaction is None


def test_poke_and_miss_you_local_reactions():
    for action in ("poke", "miss_you"):
        _, needs_ai, reaction = apply_action(
            {"grievance": 0, "dogfood": 0, "miss": 50, "intimacy": 0}, action
        )
        assert needs_ai is False
        assert reaction in LOCAL_REACTIONS[action]


def test_unknown_action_raises():
    with pytest.raises(ValueError):
        apply_action({"grievance": 0, "dogfood": 0, "miss": 0, "intimacy": 0}, "nope")


def test_apply_action_does_not_mutate_input():
    stats = {"grievance": 10, "dogfood": 0, "miss": 0, "intimacy": 0}
    apply_action(stats, "scold")
    assert stats["grievance"] == 10
