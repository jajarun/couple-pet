"""无 Alembic：sync_schema 得能给「已存在的老表」补上新增列，且重复跑无害。
这条守的是线上库——users 表早就在了，create_all 不会给它加列。"""

from sqlalchemy import create_engine, inspect, text
from sqlalchemy.pool import StaticPool

from app.schema_sync import sync_schema


def _columns(bind, table):
    return {c["name"] for c in inspect(bind).get_columns(table)}


def _engine():
    return create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )


def test_sync_creates_tables_from_scratch():
    bind = _engine()
    sync_schema(bind)
    assert "ai_reply_enabled" in _columns(bind, "users")


def test_sync_backfills_column_on_a_preexisting_table():
    bind = _engine()
    # 模拟线上：users 表已存在，但没有新列（老 schema，还带一行真实数据）
    with bind.begin() as conn:
        conn.execute(
            text(
                "CREATE TABLE users ("
                "id INTEGER PRIMARY KEY, nickname VARCHAR(64), password_hash VARCHAR(255),"
                "gender VARCHAR(8), ai_count INTEGER, ai_count_date DATE,"
                "created_at DATETIME, last_login_at DATETIME)"
            )
        )
        conn.execute(text("INSERT INTO users (id, nickname) VALUES (1, 'alice')"))
    assert "ai_reply_enabled" not in _columns(bind, "users")

    sync_schema(bind)
    assert "ai_reply_enabled" in _columns(bind, "users")
    with bind.connect() as conn:
        # 存量行回填成「关闭」，不是 NULL
        assert conn.execute(text("SELECT ai_reply_enabled FROM users WHERE id=1")).scalar() == 0


def test_sync_is_idempotent():
    bind = _engine()
    sync_schema(bind)
    sync_schema(bind)  # 第二次不该炸（重启容器会反复跑）
    assert "ai_reply_enabled" in _columns(bind, "users")
