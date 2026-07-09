"""剧情副本的编排：同回合双人抉择、解锁互看、自愈推进、一天一章、跨天顺延。

没配 DeepSeek key 时全程走 rules/stories 的本地剧本——这些用例就是在无 key 下跑的。
"""

from datetime import date

import pytest

import app.routers.story as story_router
from app.models import Story, StoryChoice, StoryRound
from tests.conftest import auth_headers

DAY = date(2026, 7, 9)


@pytest.fixture
def pair(client, monkeypatch):
    monkeypatch.setattr(story_router, "_today", lambda: DAY)
    ha = auth_headers(client, "alice")
    code = client.post("/couples", headers=ha).json()["pair_code"]
    hb = auth_headers(client, "bob")
    client.post("/couples/join", headers=hb, json={"pair_code": code})
    return ha, hb


def _get(client, h):
    r = client.get("/story", headers=h)
    assert r.status_code == 200, r.text
    return r.json()


def _choose(client, h, round_no, idx, key):
    return client.post(
        "/story/choose",
        headers=h,
        json={"round_no": round_no, "option_index": idx, "client_key": key},
    )


def _play_round(client, ha, hb, round_no):
    """两个人都选完第 round_no 幕。返回 bob 那一侧的最新响应。"""
    _choose(client, ha, round_no, 0, f"a{round_no}").raise_for_status()
    r = _choose(client, hb, round_no, 1, f"b{round_no}")
    r.raise_for_status()
    return r.json()


# ---------- 开章 ----------

def test_first_get_opens_a_chapter_with_a_playable_first_round(client, pair):
    ha, _hb = pair
    body = _get(client, ha)
    assert body["story"]["status"] == "active"
    assert body["story"]["day"] == "2026-07-09"
    assert body["story"]["total_rounds"] == 4
    assert body["story"]["title"]
    assert len(body["rounds"]) == 1
    first = body["rounds"][0]
    assert first["round_no"] == 1 and len(first["options"]) >= 2
    assert first["my_choice"] is None and body["my_turn"] is True


def test_both_of_you_land_on_the_same_chapter(client, pair):
    ha, hb = pair
    assert _get(client, ha)["story"]["id"] == _get(client, hb)["story"]["id"]


def test_repeated_gets_do_not_open_a_second_chapter(client, pair):
    ha, _hb = pair
    _get(client, ha)
    _get(client, ha)
    with client.session_factory() as s:
        assert s.query(Story).count() == 1


def test_no_couple_no_story(client):
    h = auth_headers(client, "solo")
    assert client.get("/story", headers=h).status_code == 409


# ---------- 同回合双人抉择：都选完才互看 ----------

def test_your_partners_pick_stays_hidden_until_you_pick_too(client, pair):
    ha, hb = pair
    _get(client, ha)
    _choose(client, ha, 1, 2, "a1").raise_for_status()

    seen_by_bob = _get(client, hb)["rounds"][0]
    assert seen_by_bob["my_choice"] is None
    assert seen_by_bob["partner_choice"] is None  # ← 不许偷看，否则会跟风
    assert seen_by_bob["both_chose"] is False

    seen_by_alice = _get(client, ha)["rounds"][0]
    assert seen_by_alice["my_choice"] == 2
    assert seen_by_alice["partner_choice"] is None
    assert _get(client, ha)["my_turn"] is False  # 我选完了，等 TA


def test_once_both_have_picked_the_choices_are_revealed(client, pair):
    ha, hb = pair
    _get(client, ha)
    body = _play_round(client, ha, hb, 1)
    r1 = body["rounds"][0]
    assert r1["both_chose"] is True
    assert r1["my_choice"] == 1 and r1["partner_choice"] == 0  # bob 视角

    from_alice = _get(client, ha)["rounds"][0]
    assert from_alice["my_choice"] == 0 and from_alice["partner_choice"] == 1


def test_the_second_pick_writes_the_next_round(client, pair):
    ha, hb = pair
    _get(client, ha)
    body = _play_round(client, ha, hb, 1)
    assert len(body["rounds"]) == 2
    assert body["rounds"][1]["round_no"] == 2
    assert len(body["rounds"][1]["options"]) >= 2
    assert body["my_turn"] is True  # 轮到你了


def test_the_local_next_round_echoes_what_you_both_chose(client, pair):
    ha, hb = pair
    first = _get(client, ha)["rounds"][0]
    body = _play_round(client, ha, hb, 1)
    scene = body["rounds"][1]["scene"]
    assert f"alice选了「{first['options'][0]}」" in scene
    assert f"bob选了「{first['options'][1]}」" in scene


# ---------- 幂等 / 陈旧幕 ----------

def test_replaying_the_same_choice_changes_nothing(client, pair):
    ha, _hb = pair
    _get(client, ha)
    first = _choose(client, ha, 1, 2, "same").json()
    second = _choose(client, ha, 1, 2, "same").json()
    assert first["rounds"] == second["rounds"]
    with client.session_factory() as s:
        assert s.query(StoryChoice).count() == 1


def test_your_first_pick_is_locked_in(client, pair):
    ha, _hb = pair
    _get(client, ha)
    _choose(client, ha, 1, 0, "a1").raise_for_status()
    body = _choose(client, ha, 1, 2, "a1-again").json()  # 反悔？不行
    assert body["rounds"][0]["my_choice"] == 0


def test_choosing_on_an_old_round_is_rejected(client, pair):
    ha, hb = pair
    _get(client, ha)
    _play_round(client, ha, hb, 1)
    r = _choose(client, ha, 1, 0, "late")  # 第 1 幕早翻篇了
    assert r.status_code == 409 and r.json()["detail"] == "stale_round"


def test_an_out_of_range_option_is_rejected(client, pair):
    ha, _hb = pair
    _get(client, ha)
    assert _choose(client, ha, 1, 99, "k").status_code == 422


# ---------- 自愈：竞态下没人推进，下一次 GET 补上 ----------

def test_a_get_heals_a_round_that_the_write_path_raced_past(client, pair):
    """两人几乎同时提交时，各自事务里只看得见自己那条 choice（快照隔离），两边都数到 1
    → 谁都没触发续写。这里直接绕过 choose 插入第二条 choice 来复现，然后 GET 应该把缺的
    那一幕补上——否则剧情永远卡死。"""
    ha, hb = pair
    _get(client, ha)
    _choose(client, ha, 1, 0, "a1").raise_for_status()

    with client.session_factory() as s:
        rnd = s.query(StoryRound).filter(StoryRound.round_no == 1).one()
        bob_id = 2
        s.add(StoryChoice(round_id=rnd.id, user_id=bob_id, option_index=1, client_key="sneak"))
        s.commit()
        assert s.query(StoryRound).count() == 1  # 下一幕还不存在

    body = _get(client, hb)  # 自愈
    assert len(body["rounds"]) == 2
    assert body["rounds"][1]["round_no"] == 2


def test_healing_is_idempotent_across_both_players_polling(client, pair):
    ha, hb = pair
    _get(client, ha)
    _choose(client, ha, 1, 0, "a1").raise_for_status()
    with client.session_factory() as s:
        rnd = s.query(StoryRound).filter(StoryRound.round_no == 1).one()
        s.add(StoryChoice(round_id=rnd.id, user_id=2, option_index=1, client_key="sneak"))
        s.commit()

    _get(client, ha)
    _get(client, hb)
    _get(client, ha)
    with client.session_factory() as s:
        assert s.query(StoryRound).count() == 2  # 只补一次


# ---------- 完结 ----------

def test_playing_all_four_rounds_reaches_an_ending(client, pair):
    ha, hb = pair
    _get(client, ha)
    for n in range(1, 5):
        body = _play_round(client, ha, hb, n)

    assert body["story"]["status"] == "ended"
    assert len(body["rounds"]) == 5
    ending = body["rounds"][-1]
    assert ending["round_no"] == 5 and ending["options"] == []
    assert body["my_turn"] is False


def test_the_ending_drops_exactly_one_keepsake_on_the_timeline(client, pair):
    ha, hb = pair
    title = _get(client, ha)["story"]["title"]
    for n in range(1, 5):
        _play_round(client, ha, hb, n)
    _get(client, ha)  # 再轮询几次也不该多落一条
    _get(client, hb)

    events = client.get("/events", headers=ha).json()["events"]
    keepsakes = [e for e in events if e["kind"] == "story"]
    assert len(keepsakes) == 1
    assert keepsakes[0]["content"] == title
    assert keepsakes[0]["action_type"] == "ended"


def test_nobody_can_choose_after_the_ending(client, pair):
    ha, hb = pair
    _get(client, ha)
    for n in range(1, 5):
        _play_round(client, ha, hb, n)
    assert _choose(client, ha, 5, 0, "k").status_code == 409


# ---------- 节奏：一天一章，未完成的顺延 ----------

def test_one_chapter_per_day_even_after_you_finish_it(client, pair):
    ha, hb = pair
    _get(client, ha)
    for n in range(1, 5):
        _play_round(client, ha, hb, n)
    body = _get(client, ha)  # 同一天再进来
    assert body["story"]["status"] == "ended"
    with client.session_factory() as s:
        assert s.query(Story).count() == 1


def test_a_finished_chapter_makes_room_for_a_new_one_tomorrow(client, pair, monkeypatch):
    ha, hb = pair
    first_id = _get(client, ha)["story"]["id"]
    for n in range(1, 5):
        _play_round(client, ha, hb, n)

    monkeypatch.setattr(story_router, "_today", lambda: date(2026, 7, 10))
    body = _get(client, ha)
    assert body["story"]["id"] != first_id
    assert body["story"]["status"] == "active"
    assert body["story"]["day"] == "2026-07-10"


def test_an_unfinished_chapter_carries_over_instead_of_being_scrapped(client, pair, monkeypatch):
    ha, hb = pair
    first_id = _get(client, ha)["story"]["id"]
    _play_round(client, ha, hb, 1)  # 只打了一幕

    monkeypatch.setattr(story_router, "_today", lambda: date(2026, 7, 10))
    body = _get(client, ha)
    assert body["story"]["id"] == first_id  # 还是昨天那章，接着打
    assert body["story"]["day"] == "2026-07-09"
    with client.session_factory() as s:
        assert s.query(Story).count() == 1


# ---------- 做选择算今日露面 ----------

def test_choosing_counts_as_showing_up_today(client, pair):
    ha, _hb = pair
    _get(client, ha)
    assert client.get("/daily", headers=ha).json()["streak"]["i_did_today"] is False
    _choose(client, ha, 1, 0, "a1").raise_for_status()
    assert client.get("/daily", headers=ha).json()["streak"]["i_did_today"] is True
