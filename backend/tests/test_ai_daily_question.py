from app.ai.client import AIError
from app.ai import daily_question as dq
from app.config import settings
from app.rules import daily_questions


def test_empty_key_falls_back_to_local(monkeypatch):
    monkeypatch.setattr(settings, "deepseek_api_key", "")
    text, used = dq.generate_question("deep", set(), 0)
    assert used is False
    assert text in daily_questions.LOCAL_QUESTIONS["deep"]  # 走了本地题库


def test_uses_ai_when_key_present(monkeypatch):
    monkeypatch.setattr(settings, "deepseek_api_key", "sk-test")
    monkeypatch.setattr("app.ai.daily_question.chat_completion", lambda messages: "今晚想和我做什么梦？")
    text, used = dq.generate_question("ambiguous", set(), 0)
    assert used is True
    assert text == "今晚想和我做什么梦？"


def test_ai_error_falls_back_to_local(monkeypatch):
    monkeypatch.setattr(settings, "deepseek_api_key", "sk-test")

    def boom(messages):
        raise AIError("down")

    monkeypatch.setattr("app.ai.daily_question.chat_completion", boom)
    text, used = dq.generate_question("silly", set(), 3)
    assert used is False
    assert text in daily_questions.LOCAL_QUESTIONS["silly"]


def test_empty_ai_output_falls_back(monkeypatch):
    monkeypatch.setattr(settings, "deepseek_api_key", "sk-test")
    monkeypatch.setattr("app.ai.daily_question.chat_completion", lambda messages: "   \n  ")
    text, used = dq.generate_question("deep", set(), 1)
    assert used is False
    assert text in daily_questions.LOCAL_QUESTIONS["deep"]


def test_clean_strips_numbering_and_quotes(monkeypatch):
    monkeypatch.setattr(settings, "deepseek_api_key", "sk-test")
    monkeypatch.setattr(
        "app.ai.daily_question.chat_completion",
        lambda messages: '1. “如果我变成一只猫，你会怎么养我？”\n（这里是多余的解释）',
    )
    text, used = dq.generate_question("silly", set(), 0)
    assert used is True
    assert text == "如果我变成一只猫，你会怎么养我？"  # 序号、引号、第二行解释都被清掉
