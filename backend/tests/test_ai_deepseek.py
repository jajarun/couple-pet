from app.ai.client import AIError
from app.ai.deepseek import generate_reaction
from app.config import settings

LOW = {"grievance": 0, "dogfood": 0, "miss": 0, "intimacy": 0}


def test_empty_key_falls_back_in_persona(monkeypatch):
    monkeypatch.setattr(settings, "deepseek_api_key", "")
    text, used = generate_reaction({"tone": "毒舌"}, LOW, "scold", "大猪蹄子", [])
    assert used is False
    assert "毒舌" in text  # tone-aware 兜底


def test_uses_ai_when_key_present(monkeypatch):
    monkeypatch.setattr(settings, "deepseek_api_key", "sk-test")
    monkeypatch.setattr("app.ai.deepseek.chat_completion", lambda messages: "哼，本汪偏要理你")
    text, used = generate_reaction({"tone": "毒舌"}, LOW, "chat", "在吗", [])
    assert used is True
    assert text == "哼，本汪偏要理你"


def test_ai_error_falls_back(monkeypatch):
    monkeypatch.setattr(settings, "deepseek_api_key", "sk-test")

    def boom(messages):
        raise AIError("down")

    monkeypatch.setattr("app.ai.deepseek.chat_completion", boom)
    text, used = generate_reaction({"tone": "高冷"}, LOW, "chat", "在吗", [])
    assert used is False
    assert "高冷" in text


def test_non_ai_error_also_falls_back(monkeypatch):
    monkeypatch.setattr(settings, "deepseek_api_key", "sk-test")

    def boom(messages):
        raise RuntimeError("unexpected")

    monkeypatch.setattr("app.ai.deepseek.chat_completion", boom)
    text, used = generate_reaction({"tone": "毒舌"}, LOW, "chat", "hi", [])
    assert used is False
    assert "毒舌" in text
