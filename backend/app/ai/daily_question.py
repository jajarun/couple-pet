"""每日一问的 AI 生成：按当天 flavor 拼 prompt → 调 DeepSeek → 无 key/失败回落本地题库。永不抛。

flavor 的轮换仍由 rules/daily_questions 决定；这里只负责"这一味怎么出题"，
以及把模型输出收成干净的一句话。契约同 ai/deepseek.py：绝不抛异常，出错就兜底。
"""

import re

from app.ai.client import chat_completion
from app.config import settings
from app.rules import daily_questions

# 三种 flavor 给 AI 的出题指引
_FLAVOR_BRIEF = {
    "ambiguous": "暧昧、撩人、让人心动脸红，但别低俗露骨",
    "deep": "走心、深入了解彼此、温柔真诚，能聊出心里话",
    "silly": "沙雕、无厘头、脑洞大、逗人笑",
}

_MAX_LEN = 60  # 题目控制在一句话内，超了截断


def _clean(text: str) -> str:
    """把模型输出收成干净的一句话：取首行、去序号/引号、截断。"""
    line = next((ln.strip() for ln in text.splitlines() if ln.strip()), "")
    line = re.sub(r"^\s*\d+[.、)）]\s*", "", line)  # 去行首 "1. " "1、" "1) "
    line = re.sub(r"^[-*·]\s*", "", line)  # 去 "- " "· "
    line = line.strip(" \t　\"'“”‘’「」『』")  # 去两端引号/书名号/全角空格
    return line[:_MAX_LEN].strip()


def _build_messages(flavor: str, recent: set[str]) -> list[dict]:
    brief = _FLAVOR_BRIEF.get(flavor, "有趣、适合情侣互答")
    avoid = "；".join(list(recent)[:8])
    avoid_line = f"\n最近出过、务必避开：{avoid}" if avoid else ""
    system = (
        "你在给一对情侣出「每日一问」——一道两个人都会作答、然后互看答案的小问题。"
        "只输出问题本身：一句话、中文口语、不超过 30 字，"
        "不要序号、不要引号、不要任何解释或多余的话。"
    )
    user = f"出一道{brief}的情侣问题。{avoid_line}"
    return [
        {"role": "system", "content": system},
        {"role": "user", "content": user},
    ]


def generate_question(flavor: str, recent: set[str], seed: int) -> tuple[str, bool]:
    """返回 (题目文本, used_ai)。无 key 或任何异常都回落本地题库，永不抛。

    注：每日一问是每对每天一次的共享资源，不计入个人 AI 次数上限（不碰 quota）。
    """
    if not settings.deepseek_api_key:
        return daily_questions.pick_local(flavor, recent, seed), False
    try:
        text = _clean(chat_completion(_build_messages(flavor, recent)))
        if not text:
            raise ValueError("empty after clean")
        return text, True
    except Exception:
        return daily_questions.pick_local(flavor, recent, seed), False
