# 情侣分身宠物 · 前端

像素电子宠物机风格的移动端 web 前端，消费 `../backend` 的 FastAPI。

## 本地运行

1. 起后端（另一个终端）：
   ```bash
   cd backend && .venv/bin/uvicorn app.main:app --reload --port 8000
   ```
2. 起前端：
   ```bash
   cd frontend && pnpm install && pnpm dev
   ```
   开发期 Vite 把 `/api/*` 代理到 `http://localhost:8000/*`。

## 测试

```bash
cd frontend && pnpm test         # vitest 一次性跑
pnpm exec tsc -b                      # 类型检查
```

## 双人真配对试玩

见 `../docs/couple-playtest-checklist.md`。需要两个账号 / 两台设备（或两个隐身窗口）。
