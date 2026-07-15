"""部署护栏：`.env.example` 上文档化的旋钮，必须真的能拧动线上。

**镜像里没有 `.env`**（backend/Dockerfile 只 COPY app/ + entrypoint），所以
config.py 的 `env_file=".env"` 在容器里读了个寂寞。变量能进容器的唯一通道是
docker-compose.yml 里 backend 服务的 `environment:` 块。

漏一行的症状极其安静：`.env` 里写 `STORY_ROUNDS=8`，重启，线上仍然是 4 幕，
没有任何报错。这条测试就是那声报错。
"""

import re
from pathlib import Path

import pytest

from app.config import Settings

_ROOT = Path(__file__).resolve().parents[2]
_ENV_EXAMPLE = _ROOT / ".env.example"
_COMPOSE = _ROOT / "docker-compose.yml"


def _documented_keys() -> list[str]:
    """.env.example 里所有 KEY=...（跳过注释行）。"""
    text = _ENV_EXAMPLE.read_text(encoding="utf-8")
    return re.findall(r"^([A-Z][A-Z0-9_]*)=", text, flags=re.MULTILINE)


def _backend_env_block() -> str:
    """docker-compose.yml 里 backend 服务的 environment: 块（到下一个同级键为止）。"""
    text = _COMPOSE.read_text(encoding="utf-8")
    m = re.search(r"^    environment:\n(.*?)(?=^    \w)", text, flags=re.MULTILINE | re.DOTALL)
    assert m, "没找到 backend 的 environment 块——compose 结构变了？"
    return m.group(1)


def test_every_documented_setting_reaches_the_container():
    """`.env.example` 里凡是对得上 Settings 字段的键，compose 都得传进去。"""
    settings_fields = set(Settings.model_fields)
    block = _backend_env_block()

    missing = [
        key
        for key in _documented_keys()
        if key.lower() in settings_fields and not re.search(rf"^      {key}:", block, re.MULTILINE)
    ]
    assert not missing, (
        f"这些键写在 .env.example 里、也是 Settings 字段，但没进 docker-compose.yml 的 "
        f"backend environment——线上永远拿默认值：{missing}"
    )


@pytest.mark.parametrize("key", ["STORY_ROUNDS", "PRESENCE_TTL_SECONDS", "ENABLE_SCHEDULER", "DREAM_HOUR"])
def test_the_four_that_were_actually_missing(key):
    """回归：这四个曾经只写了 .env.example、没写 compose，线上改不动。"""
    assert re.search(rf"^      {key}:", _backend_env_block(), re.MULTILINE)


def test_the_image_really_has_no_dotenv():
    """上面那套推理的前提。哪天 Dockerfile 开始 COPY .env 了，这条会提醒你回来改注释。"""
    dockerfile = (_ROOT / "backend" / "Dockerfile").read_text(encoding="utf-8")
    assert not re.search(r"^COPY\s+.*\.env", dockerfile, re.MULTILINE)
