import pytest

from app.rules.evolution import (
    BALANCED,
    MAX_STAGE,
    STAGE_THRESHOLDS,
    decide_branch,
    empty_state,
    evolve,
    exp_of,
    record_care,
    stage_of,
    view,
)

NOW = "2026-07-09T12:00:00"


def test_empty_state_shape():
    assert empty_state() == {"stage": 0, "branch": "", "exp": 0, "care": {}, "history": []}


def test_record_care_counts_up_without_mutating_input():
    care = {"hug": 1}
    out = record_care(care, "hug")
    assert out == {"hug": 2}
    assert care == {"hug": 1}


def test_exp_of_weights_actions():
    # poke=1, chat=2, hug=3
    assert exp_of({"poke": 2, "chat": 1, "hug": 3}) == 2 + 2 + 9


def test_exp_of_ignores_unknown_actions():
    assert exp_of({"nudge": 100}) == 0


@pytest.mark.parametrize(
    "exp,expected",
    [(0, 0), (9, 0), (10, 1), (39, 1), (40, 2), (119, 2), (120, 3), (9999, 3)],
)
def test_stage_of_boundaries(exp, expected):
    assert stage_of(exp) == expected


def test_stage_thresholds_line_up_with_max_stage():
    assert len(STAGE_THRESHOLDS) - 1 == MAX_STAGE


def test_decide_branch_hits_each_branch():
    assert decide_branch({"hug": 10}) == "sweet"
    assert decide_branch({"feed_dogfood": 10}) == "glutton"
    assert decide_branch({"scold": 6, "poke": 4}) == "dark"
    assert decide_branch({"chat": 10}) == "chatty"


def test_decide_branch_counts_coax_as_sweet():
    assert decide_branch({"coax": 3, "chat": 2}) == "sweet"


def test_decide_branch_empty_care_is_balanced():
    assert decide_branch({}) == BALANCED


def test_decide_branch_tie_is_balanced():
    assert decide_branch({"hug": 5, "chat": 5}) == BALANCED


def test_decide_branch_dominance_threshold():
    # 9/20 = 0.45 → 刚好够，定型；8/20 = 0.40 → 不够，均衡
    assert decide_branch({"scold": 9, "chat": 6, "hug": 5}) == "dark"
    assert decide_branch({"scold": 8, "chat": 6, "hug": 6}) == BALANCED


def test_evolve_does_not_mutate_input():
    evo = empty_state()
    evolve(evo, "hug", NOW)
    assert evo == empty_state()


def test_evolve_flags_only_the_crossing_action():
    evo = empty_state()
    # hug=3 exp/次；连喂 3 次 → exp 9，还在 stage 0
    for _ in range(3):
        evo, evolved = evolve(evo, "hug", NOW)
        assert evolved is False
    assert evo["exp"] == 9 and evo["stage"] == 0
    evo, evolved = evolve(evo, "hug", NOW)  # exp 12 → 破壳
    assert evolved is True and evo["stage"] == 1


def test_evolve_appends_history_only_on_evolution():
    evo = empty_state()
    evo, _ = evolve(evo, "hug", NOW)
    assert evo["history"] == []
    for _ in range(3):
        evo, _ = evolve(evo, "hug", NOW)
    assert evo["history"] == [{"stage": 1, "branch": "", "at": NOW}]


def _grind(evo, action, times):
    for _ in range(times):
        evo, _ = evolve(evo, action, NOW)
    return evo


def test_branch_locks_in_at_adult_stage_and_is_irreversible():
    evo = _grind(empty_state(), "scold", 40)  # exp 40 → stage 2，全是骂 → dark
    assert evo["stage"] == 2 and evo["branch"] == "dark"
    # 之后狂喂狗粮也扳不回来：分支只在首次进成体时定型
    evo = _grind(evo, "feed_dogfood", 30)
    assert evo["branch"] == "dark"
    assert evo["stage"] == 3  # 40 + 90 = 130 exp


def test_branch_is_empty_before_adult():
    evo = _grind(empty_state(), "hug", 4)  # exp 12 → stage 1
    assert evo["stage"] == 1 and evo["branch"] == ""


def test_view_of_fresh_egg():
    assert view(empty_state()) == {
        "stage": 0,
        "branch": "",
        "exp": 0,
        "next_exp": 10,
        "progress": 0.0,
        "emoji": "🥚",
        "title": "一颗蛋",
        "use_form_emoji": False,
    }


def test_view_tolerates_none_and_empty_legacy_data():
    assert view(None) == view({}) == view(empty_state())


def test_view_progress_within_stage():
    evo = _grind(empty_state(), "poke", 5)  # exp 5，stage 0，区间 [0,10)
    assert view(evo)["progress"] == 0.5


def test_view_at_max_stage_has_no_next():
    evo = _grind(empty_state(), "hug", 40)  # exp 120 → 完全体
    v = view(evo)
    assert v["stage"] == MAX_STAGE
    assert v["next_exp"] is None and v["progress"] == 1.0


def test_view_uses_form_emoji_from_adult_stage():
    kid = view(_grind(empty_state(), "hug", 4))
    assert kid["use_form_emoji"] is False and kid["emoji"] == "🐣"
    adult = view(_grind(empty_state(), "scold", 40))
    assert adult["use_form_emoji"] is True
    assert adult["emoji"] == "😼" and adult["title"] == "腹黑体"


def test_view_falls_back_to_balanced_form_when_branch_missing_at_adult():
    # 理论上不该发生（evolve 会定型），但老数据/手改库不该让首页拿到「神秘体」
    v = view({"stage": 2, "branch": "", "exp": 50, "care": {}, "history": []})
    assert v["branch"] == BALANCED and v["emoji"] == "🐱"
