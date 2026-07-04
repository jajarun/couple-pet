# 一键启动（Docker）

三个容器：`db`（MySQL 8）、`backend`（FastAPI/uvicorn）、`web`（nginx 托管前端静态产物 + 反代 `/api`）。前端 **在本地 pnpm 打包**成 `frontend/dist`，nginx bind-mount 这个本地目录来托管，不进镜像。

## 跑起来

```bash
cp .env.example .env      # 可选，改端口/密码/DeepSeek key
./start.sh                # 打包前端 + docker compose up（前台）
# 或后台：./start.sh -d
```

打开 **http://localhost**（端口 `WEB_PORT`，默认 `80`；被占用就在 `.env` 改成 8080 等）。

## 手机 / 局域网访问

同一路由器下,手机、平板都能直接访问这台 Mac 上的服务。前端调用 `/api` 是**相对路径**、经 nginx 同源反代后端,所以用哪个地址进来 API 就走哪个,**不用改任何代码、不涉及 CORS**。

1. **用 IP** — 先查 Mac 的局域网地址:`ipconfig getifaddr en0`,手机浏览器打开 `http://<那个IP>`(端口 80 可省略)。
2. **用本地域名(推荐,IP 变了也不怕)** — macOS 通过 Bonjour/mDNS 自动广播 `<主机名>.local`:
   ```bash
   scutil --get LocalHostName        # 看当前名字
   sudo scutil --set LocalHostName pet   # 可选:改成好记的短名
   ```
   然后手机打开 `http://pet.local`。**iPhone/iPad/Mac 原生支持 `.local`**。
3. **安卓 / 想让所有设备都稳** — 安卓 Chrome 对 `.local`(mDNS)解析不稳。更稳的办法:在**路由器后台**给这台 Mac 做 **IP 绑定/静态租约**,再加一条**静态 DNS / 域名映射** `pet.lan → <Mac的IP>`,所有设备都能用 `http://pet.lan`。

排障:

- 手机打不开 → 确认手机和 Mac 在**同一 Wi-Fi**,且路由器没开 **AP 隔离 / 访客网络隔离**。
- macOS 防火墙若开着,首次访问放行 Docker。查状态:`/usr/libexec/ApplicationFirewall/socketfilterfw --getglobalstate`。
- **本机用 `curl <名字>.local` 报 502 但手机正常** → 是你 Mac 终端设了 `http_proxy`(如 Clash),`.local` 不在 `NO_PROXY` 白名单被塞进代理导致的,**跟服务无关**,手机没这代理不受影响。

## 架构

```
浏览器 → nginx:80 ────┬── /            静态前端 (frontend/dist, SPA 回退 index.html)
                      └── /api/*       反代 → backend:8000/*   (去掉 /api 前缀)
backend:8000 → db:3306 (MySQL, utf8mb4)
```

- 同源访问（前端和 `/api` 同一入口），**不需要 CORS**。
- 后端也映射到 `localhost:8000` 方便直连调试；MySQL 映射到 `localhost:3306`。
- 首次启动后端 entrypoint 会按模型建表（暂无 Alembic 迁移），带重试等 MySQL 就绪。
- Chinese 文本：MySQL 与连接串都用 `utf8mb4`。

## 常用命令

```bash
docker compose up --build -d     # 后台起（需先 pnpm -C frontend build）
docker compose logs -f backend   # 看后端日志
docker compose down              # 停（保留数据卷）
docker compose down -v           # 停并清空数据库数据卷
```

## 改了前端后

重新打包再让 nginx 生效（静态文件是 bind-mount，无需重建镜像）：

```bash
pnpm -C frontend build
```

## 点亮真 DeepSeek

在 `.env` 填 `DEEPSEEK_API_KEY=sk-...` 再 `docker compose up -d backend`。留空则 scold/chat 走离线沙雕兜底。
