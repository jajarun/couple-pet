#!/usr/bin/env bash
# 一键启动：打包前端 → 起 db + backend（默认再加自带 nginx）。
# 用法：
#   ./start.sh              前台启动全套（db + backend + nginx，Ctrl-C 停）
#   ./start.sh -d           后台启动
#   ./start.sh --build      强制重建镜像
#   ./start.sh --no-web     不起自带 nginx，只跑 db + backend 并暴露后端端口
#                           （生产已有自己的 nginx 时用：由它托管 frontend/dist + 反代 /api + 挂 HTTPS）
#                           别名：--no-nginx / --backend-only
set -euo pipefail
cd "$(dirname "$0")"

# 读 .env 让下面的端口提示和 compose 用同一套值（compose 本身也会自动读 .env）
[ -f .env ] && { set -a; . ./.env; set +a; }

# 摘掉自定义开关（docker compose 不认识它们），其余原样透传给 compose
WITH_WEB=1
ARGS=()
for a in "$@"; do
  case "$a" in
    --no-web|--no-nginx|--backend-only) WITH_WEB=0 ;;
    *) ARGS+=("$a") ;;
  esac
done

echo "▶ 1/2 打包前端（pnpm build → frontend/dist）…"
pnpm -C frontend install --frozen-lockfile
pnpm -C frontend build

if [ "$WITH_WEB" = 1 ]; then
  echo "▶ 2/2 启动 docker compose（db + backend + nginx）…"
  docker compose --profile web up --build ${ARGS[@]+"${ARGS[@]}"}
else
  echo "▶ 2/2 启动 docker compose（db + backend，不含 nginx）…"
  docker compose up --build ${ARGS[@]+"${ARGS[@]}"}
fi

echo ""
if [ "$WITH_WEB" = 1 ]; then
  echo "✔ 入口: http://localhost:${WEB_PORT:-80}   (后端直连: http://localhost:${BACKEND_PORT:-8000})"
  echo "   局域网: http://$(ipconfig getifaddr en0 2>/dev/null || echo '<本机IP>'):${WEB_PORT:-80}"
else
  echo "✔ 后端已暴露: http://localhost:${BACKEND_PORT:-8000}"
  echo "   前端 frontend/dist 已打包好，交给你自己的 nginx 托管 + 反代 /api → 127.0.0.1:${BACKEND_PORT:-8000}"
fi
