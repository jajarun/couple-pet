from app.rules.stories import CHOICE_ROUNDS, LOCAL_STORIES, local_ending, local_round, pick_story


def test_every_local_story_is_playable_end_to_end():
    for s in LOCAL_STORIES:
        assert s["title"] and s["ending"]
        assert len(s["rounds"]) == CHOICE_ROUNDS
        for r in s["rounds"]:
            assert r["scene"]
            assert 2 <= len(r["options"]) <= 3
            assert len(set(r["options"])) == len(r["options"])


def test_titles_are_unique():
    titles = [s["title"] for s in LOCAL_STORIES]
    assert len(set(titles)) == len(titles)


def test_pick_story_is_deterministic_and_wraps():
    assert pick_story(3) is pick_story(3)
    assert pick_story(0) is pick_story(len(LOCAL_STORIES))


def test_local_round_returns_scene_and_options():
    s = pick_story(0)
    r = local_round(s, 1)
    assert r["scene"] == s["rounds"][0]["scene"]
    assert r["options"] == s["rounds"][0]["options"]


def test_local_round_does_not_leak_the_stored_list():
    """返回的是副本——调用方（router）会把它塞进 JSON 列，别让它改到剧本库。"""
    s = pick_story(0)
    local_round(s, 1)["options"].append("乱来")
    assert len(s["rounds"][0]["options"]) <= 3


def test_past_the_last_round_is_the_ending_with_no_options():
    s = pick_story(1)
    r = local_round(s, CHOICE_ROUNDS + 1)
    assert r["options"] == []
    assert r["scene"] == local_ending(s)


def test_round_zero_is_also_the_ending_not_a_crash():
    s = pick_story(2)
    assert local_round(s, 0)["options"] == []
