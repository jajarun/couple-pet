#!/bin/sh
set -e

# 还没有 Alembic 迁移——启动时按模型对齐 schema：建表 + 给老表补新增列（都幂等）。
# MySQL 首次启动初始化可能比 healthcheck 稍慢，带重试。
echo "▶ 确保数据库表存在…"
tries=0
until python -c "from app.schema_sync import sync_schema; sync_schema()" 2>/dev/null; do
  tries=$((tries + 1))
  if [ "$tries" -ge 30 ]; then
    echo "✖ 数据库 30 次重试仍不可达，放弃" >&2
    exit 1
  fi
  echo "  数据库还没准备好 ($tries/30)，2s 后重试…"
  sleep 2
done
echo "✔ 表已就绪"

exec uvicorn app.main:app --host 0.0.0.0 --port "${APP_PORT:-8000}"
