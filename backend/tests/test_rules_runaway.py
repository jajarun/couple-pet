import pytest

from app.rules.runaway import (
    HOSTILE,
    HOSTILE_THRESHOLD,
    SOOTHE,
    is_away,
    should_run_away,
)


def test_hostile_and_soothe_buckets_do_not_overlap():
    assert not set(HOSTILE) & set(SOOTHE)


def test_runs_away_after_enough_hostility_with_no_comfort():
    assert should_run_away(HOSTILE_THRESHOLD, 0, already_away=False) is True


@pytest.mark.parametrize("hostile", [0, 1, HOSTILE_THRESHOLD - 1])
def test_stays_when_hostility_is_below_the_line(hostile):
    assert should_run_away(hostile, 0, already_away=False) is False


def test_one_comforting_gesture_forgives_everything():
    assert should_run_away(99, 1, already_away=False) is False


def test_already_gone_does_not_run_away_twice():
    assert should_run_away(99, 0, already_away=True) is False


def test_is_away_reads_the_event_stream():
    assert is_away(None, None) is False          # 从没跑过
    assert is_away(10, None) is True             # 跑了，还没哄
    assert is_away(10, 11) is False              # 哄回来了
    assert is_away(12, 11) is True               # 哄回来又跑了
    assert is_away(None, 11) is False            # 只有 coax（理论上不该出现）
