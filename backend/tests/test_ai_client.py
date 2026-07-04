import httpx
import pytest

from app.ai.client import AIError, chat_completion
from app.config import settings


def test_deepseek_settings_have_defaults():
    assert settings.deepseek_base_url == "https://api.deepseek.com"
    assert settings.deepseek_model == "deepseek-chat"
    assert settings.deepseek_timeout_seconds == 8
    assert settings.deepseek_max_tokens == 200
    assert settings.deepseek_temperature == 1.3
    assert settings.deepseek_recent_context == 10


def _client(handler):
    return httpx.Client(transport=httpx.MockTransport(handler), base_url="http://test")


def test_chat_completion_parses_reply():
    def handler(request):
        return httpx.Response(200, json={"choices": [{"message": {"content": "喵喵"}}]})

    text = chat_completion([{"role": "user", "content": "hi"}], http_client=_client(handler))
    assert text == "喵喵"


def test_chat_completion_raises_on_non_200():
    def handler(request):
        return httpx.Response(500, json={"error": "boom"})

    with pytest.raises(AIError):
        chat_completion([{"role": "user", "content": "hi"}], http_client=_client(handler))


def test_chat_completion_raises_on_empty_choices():
    def handler(request):
        return httpx.Response(200, json={"choices": []})

    with pytest.raises(AIError):
        chat_completion([{"role": "user", "content": "hi"}], http_client=_client(handler))


def test_chat_completion_raises_on_blank_content():
    def handler(request):
        return httpx.Response(200, json={"choices": [{"message": {"content": "   "}}]})

    with pytest.raises(AIError):
        chat_completion([{"role": "user", "content": "hi"}], http_client=_client(handler))


def test_chat_completion_raises_on_timeout():
    def handler(request):
        raise httpx.TimeoutException("slow")

    with pytest.raises(AIError):
        chat_completion([{"role": "user", "content": "hi"}], http_client=_client(handler))


def test_chat_completion_raises_on_unparseable_body():
    def handler(request):
        return httpx.Response(200, content=b"not json")

    with pytest.raises(AIError):
        chat_completion([{"role": "user", "content": "hi"}], http_client=_client(handler))


def test_chat_completion_raises_on_null_body():
    def handler(request):
        return httpx.Response(200, json=None)

    with pytest.raises(AIError):
        chat_completion([{"role": "user", "content": "hi"}], http_client=_client(handler))


def test_chat_completion_raises_on_non_dict_choice():
    def handler(request):
        return httpx.Response(200, json={"choices": ["x"]})

    with pytest.raises(AIError):
        chat_completion([{"role": "user", "content": "hi"}], http_client=_client(handler))
