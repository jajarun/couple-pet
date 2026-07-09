import app.ai.dream as dream_mod
from app.ai.dream import generate_dream, generate_runaway_note
from app.rules.dreams import LOCAL_DREAMS, LOCAL_RUNAWAY_NOTES

PERSONA = {"tone": ["毒舌"], "seed": "爱吃醋", "gender": "female"}
STATS = {"grievance": 90, "dogfood": 0, "miss": 0, "intimacy": 0}


def test_no_key_falls_back_to_local_pool(monkeypatch):
    monkeypatch.setattr(dream_mod.settings, "deepseek_api_key", "")
    text, used_ai = generate_dream(PERSONA, "dark", STATS, 0)
    assert used_ai is False
    assert text in LOCAL_DREAMS["dark"]


def test_ai_failure_falls_back_and_never_raises(monkeypatch):
    monkeypatch.setattr(dream_mod.settings, "deepseek_api_key", "sk-x")
    monkeypatch.setattr(dream_mod, "chat_completion", lambda m: (_ for _ in ()).throw(RuntimeError("boom")))
    text, used_ai = generate_dream(PERSONA, "glutton", STATS, 1)
    assert used_ai is False
    assert text in LOCAL_DREAMS["glutton"]


def test_blank_ai_output_falls_back(monkeypatch):
    monkeypatch.setattr(dream_mod.settings, "deepseek_api_key", "sk-x")
    monkeypatch.setattr(dream_mod, "chat_completion", lambda m: "   \n  ")
    text, used_ai = generate_dream(PERSONA, "sweet", STATS, 2)
    assert used_ai is False
    assert text in LOCAL_DREAMS["sweet"]


def test_ai_output_is_cleaned_and_capped(monkeypatch):
    monkeypatch.setattr(dream_mod.settings, "deepseek_api_key", "sk-x")
    monkeypatch.setattr(dream_mod, "chat_completion", lambda m: '1. 「（翻身）别走…」\n多余的第二行')
    text, used_ai = generate_dream(PERSONA, "sweet", STATS, 0)
    assert used_ai is True
    assert text == "（翻身）别走…"


def test_prompt_carries_persona_mood_and_form(monkeypatch):
    monkeypatch.setattr(dream_mod.settings, "deepseek_api_key", "sk-x")
    seen = {}

    def fake(messages):
        seen["system"] = messages[0]["content"]
        return "（呓语）唔…"

    monkeypatch.setattr(dream_mod, "chat_completion", fake)
    generate_dream(PERSONA, "dark", STATS, 0)
    assert "毒舌" in seen["system"] and "爱吃醋" in seen["system"]
    assert "黑化" in seen["system"]  # 形态改写它连做梦的口吻
    assert "委屈" in seen["system"]  # 此刻心情


def test_dreams_are_a_shared_resource_and_never_touch_personal_quota():
    """同每日一问出题：情侣级共享资源，不占任何人的每日 AI 额度。

    直接查模块命名空间——`from app.ai.quota import ...` 在 import 时就绑定了，
    只 monkeypatch app.ai.quota 拦不住它。
    """
    for name in ("quota", "record_ai_usage", "ai_quota_available"):
        assert not hasattr(dream_mod, name), f"ai/dream.py 不该碰 quota，却引入了 {name}"


def test_runaway_note_no_key_falls_back(monkeypatch):
    monkeypatch.setattr(dream_mod.settings, "deepseek_api_key", "")
    text, used_ai = generate_runaway_note(PERSONA, "chatty", 0)
    assert used_ai is False
    assert text in LOCAL_RUNAWAY_NOTES["chatty"]


def test_runaway_note_prompt_is_about_leaving(monkeypatch):
    monkeypatch.setattr(dream_mod.settings, "deepseek_api_key", "sk-x")
    seen = {}
    monkeypatch.setattr(dream_mod, "chat_completion", lambda m: seen.update(system=m[0]["content"]) or "走了。")
    text, used_ai = generate_runaway_note(PERSONA, "dark", 0)
    assert used_ai is True and text == "走了。"
    assert "离家出走" in seen["system"] and "纸条" in seen["system"]
