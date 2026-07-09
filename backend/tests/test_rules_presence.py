from datetime import datetime, timedelta

from app.rules.presence import is_online

NOW = datetime(2026, 7, 9, 12, 0, 0)


def test_never_seen_is_offline():
    assert is_online(None, NOW, 25) is False


def test_fresh_heartbeat_is_online():
    assert is_online(NOW - timedelta(seconds=3), NOW, 25) is True


def test_exactly_at_the_ttl_still_counts():
    assert is_online(NOW - timedelta(seconds=25), NOW, 25) is True


def test_one_second_past_the_ttl_goes_dark():
    assert is_online(NOW - timedelta(seconds=26), NOW, 25) is False


def test_a_clock_skewed_future_heartbeat_is_online():
    """对方的时钟快了一点也不该把 TA 判成离线。"""
    assert is_online(NOW + timedelta(seconds=2), NOW, 25) is True
