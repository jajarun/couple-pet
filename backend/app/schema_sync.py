"""无 Alembic：启动时幂等对齐 schema —— 建缺失的表 + 给已存在的老表补新增列。

`create_all` 只建「表」，绝不给已存在的表加「列」。线上库里 users 表早就有了，
所以给老模型新增字段必须在这里补一行，否则线上 `SELECT users.*` 会报 Unknown column。
"""

from sqlalchemy import inspect, text

import app.models  # noqa: F401 —— 注册 Base.metadata 上的表
from app.db import Base, engine

# (表名, 列名, 建列 DDL)——DDL 写法须 SQLite / MySQL 通用
_ADDED_COLUMNS = [
    ("users", "ai_reply_enabled", "BOOLEAN NOT NULL DEFAULT 0"),
    ("users", "last_seen_at", "DATETIME NULL"),
]


def sync_schema(bind=engine) -> None:
    Base.metadata.create_all(bind)
    insp = inspect(bind)
    tables = set(insp.get_table_names())
    for table, column, ddl in _ADDED_COLUMNS:
        if table not in tables:
            continue  # create_all 刚建的新表，本来就含该列
        if column in {c["name"] for c in insp.get_columns(table)}:
            continue
        with bind.begin() as conn:
            conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {column} {ddl}"))
