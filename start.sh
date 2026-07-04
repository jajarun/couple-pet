#!/usr/bin/env bash
# 一键启动：打包前端 → 起 db + backend + nginx。
# 用法：
#   ./start.sh          前台启动（Ctrl-C 停）
#   ./start.sh -d       后台启动
#   ./start.sh --build  强制重建镜像
set -euo pipefail
cd "$(dirname "$0")"

# 读 .env 让下面的端口提示和 compose 用同一套值（compose 本身也会自动读 .env）
[ -f .env ] && { set -a; . ./.env; set +a; }

echo "▶ 1/2 打包前端（pnpm build → frontend/dist）…"
pnpm -C frontend install --frozen-lockfile
pnpm -C frontend build

echo "▶ 2/2 启动 docker compose（db + backend + nginx）…"
docker compose up --build "$@"

echo ""
echo "✔ 入口: http://localhost:${WEB_PORT:-80}   (后端直连: http://localhost:${BACKEND_PORT:-8000})"
echo "   局域网: http://$(ipconfig getifaddr en0 2>/dev/null || echo '<本机IP>'):${WEB_PORT:-80}"
