"""DeepSeek 调用封装（与 OpenAI 兼容）。只调用+解析+抛 AIError，不做兜底。"""

import httpx

from app.config import settings


class AIError(Exception):
    """DeepSeek 调用失败——上层据此落地本地兜底。"""


def _build_client() -> httpx.Client:
    return httpx.Client(
        base_url=settings.deepseek_base_url,
        timeout=settings.deepseek_timeout_seconds,
    )


def chat_completion(
    messages: list[dict],
    *,
    http_client: httpx.Client | None = None,
    max_tokens: int | None = None,
    temperature: float | None = None,
) -> str:
    """max_tokens / temperature 不传就取 settings 里的默认（200 / 1.3，为一句话的分身回话调的）。

    需要长文本或稳定格式的调用方（如剧情副本的续写）自己传：短 token 会把故事拦腰截断，
    高 temperature 会把「场景：…／A. …」这种严格格式写崩。
    """
    client = http_client or _build_client()
    try:
        try:
            resp = client.post(
                "/chat/completions",
                headers={"Authorization": f"Bearer {settings.deepseek_api_key}"},
                json={
                    "model": settings.deepseek_model,
                    "messages": messages,
                    "max_tokens": (
                        max_tokens if max_tokens is not None else settings.deepseek_max_tokens
                    ),
                    "temperature": (
                        temperature if temperature is not None else settings.deepseek_temperature
                    ),
                    "stream": False,
                },
            )
        except httpx.HTTPError as e:  # 超时 / 连接错误等（TimeoutException 是其子类）
            raise AIError(str(e)) from e
        if resp.status_code != 200:
            raise AIError(f"status {resp.status_code}")
        try:
            data = resp.json()
        except ValueError as e:
            raise AIError("bad json") from e
        try:
            choices = data.get("choices") or []
            if not choices:
                raise AIError("no choices")
            text = ((choices[0].get("message") or {}).get("content") or "").strip()
        except (AttributeError, TypeError, KeyError, IndexError) as e:
            raise AIError("bad shape") from e
        if not text:
            raise AIError("empty content")
        return text
    finally:
        if http_client is None:
            client.close()
