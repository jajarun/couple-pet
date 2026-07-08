from app.rules.daily_questions import (
    FLAVORS,
    LOCAL_QUESTIONS,
    choose_flavor,
    pick_local,
)


def test_three_flavors_each_have_enough_unique_lines():
    assert FLAVORS == ["ambiguous", "deep", "silly"]
    for flavor in FLAVORS:
        lines = LOCAL_QUESTIONS[flavor]
        assert len(lines) >= 8, f"{flavor} 只有 {len(lines)} 条"
        assert len(set(lines)) == len(lines), f"{flavor} 有重复"


def test_choose_flavor_is_deterministic_and_cycles():
    assert choose_flavor(0) == "ambiguous"
    assert choose_flavor(1) == "deep"
    assert choose_flavor(2) == "silly"
    assert choose_flavor(3) == "ambiguous"


def test_pick_local_returns_a_line_from_that_flavor():
    q = pick_local("silly", set(), seed=0)
    assert q in LOCAL_QUESTIONS["silly"]


def test_pick_local_avoids_excluded_when_possible():
    bank = LOCAL_QUESTIONS["deep"]
    exclude = set(bank[:-1])  # 只留最后一条没被排除
    q = pick_local("deep", exclude, seed=0)
    assert q == bank[-1]


def test_pick_local_falls_back_when_all_excluded():
    bank = LOCAL_QUESTIONS["deep"]
    q = pick_local("deep", set(bank), seed=0)  # 全排除也得给一句
    assert q in bank
