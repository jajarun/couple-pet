from app.rules.stats import (
    STAT_KEYS,
    DEFAULT_STATS,
    GRIEVANCE_THRESHOLD,
    clamp,
    apply_time_decay,
    needs_comfort,
)


def test_stat_keys_and_defaults():
    assert STAT_KEYS == ["grievance", "dogfood", "miss", "intimacy"]
    assert DEFAULT_STATS == {"grievance": 0, "dogfood": 0, "miss": 0, "intimacy": 0}


def test_clamp_bounds_and_int():
    assert clamp(-5) == 0
    assert clamp(150) == 100
    assert clamp(42.9) == 43      # round-half-up (was truncation)
    assert clamp(42.4) == 42
    assert clamp(42.5) == 43
    assert isinstance(clamp(42.9), int)


def test_time_decay_miss_rises_grievance_and_dogfood_fall():
    stats = {"grievance": 50, "dogfood": 30, "miss": 10, "intimacy": 60}
    out = apply_time_decay(stats, 3600.0)  # one hour
    assert out["miss"] == 14        # +4/hr
    assert out["grievance"] == 48   # -2/hr
    assert out["dogfood"] == 29     # -1/hr
    assert out["intimacy"] == 60    # never changes with time


def test_time_decay_clamps_at_zero():
    stats = {"grievance": 1, "dogfood": 0, "miss": 0, "intimacy": 0}
    out = apply_time_decay(stats, 3600.0)
    assert out["grievance"] == 0
    assert out["dogfood"] == 0


def test_time_decay_does_not_mutate_input():
    stats = {"grievance": 50, "dogfood": 30, "miss": 10, "intimacy": 60}
    apply_time_decay(stats, 3600.0)
    assert stats["miss"] == 10


def test_needs_comfort_threshold():
    assert needs_comfort({"grievance": 80, "dogfood": 0, "miss": 0, "intimacy": 0}) is True
    assert needs_comfort({"grievance": 79, "dogfood": 0, "miss": 0, "intimacy": 0}) is False
