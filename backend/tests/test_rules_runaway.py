import pytest

from app.rules.runaway import (
    AWAY,
    HOME,
    HOSTILE,
    HOSTILE_THRESHOLD,
    PENDING,
    SOOTHE,
    should_run_away,
    state_of,
)


def test_hostile_and_soothe_buckets_do_not_overlap():
    assert not set(HOSTILE) & set(SOOTHE)


def test_only_scolding_counts_as_hostility():
    """首页点一下分身发的就是 poke——手滑五下不该把它逼走。"""
    assert HOSTILE == ("scold",)


def test_runs_away_after_enough_hostility_with_no_comfort():
    assert should_run_away(HOSTILE_THRESHOLD, 0) is True


@pytest.mark.parametrize("hostile", [0, 1, HOSTILE_THRESHOLD - 1])
def test_stays_when_hostility_is_below_the_line(hostile):
    assert should_run_away(hostile, 0) is False


def test_one_comforting_gesture_forgives_everything():
    assert should_run_away(99, 1) is False


def test_state_reads_the_event_stream():
    assert state_of(None, None, None) == HOME  # 从没跑过
    assert state_of(10, None, None) == AWAY  # 跑了，还没人哄
    assert state_of(10, 11, None) == PENDING  # 哄过了，等对方点头
    assert state_of(10, 11, 12) == HOME  # 对方点了头，回来了
    assert state_of(13, 11, 12) == AWAY  # 回来又被气跑了
    assert state_of(None, None, 12) == HOME  # 只有 forgive（理论上不该出现）


def test_coaxing_alone_never_brings_it_home():
    """这是本次规则改动的核心：哄完只是 pending，钥匙在对方手里。"""
    assert state_of(10, 11, None) != HOME
    assert state_of(10, 99, None) == PENDING
