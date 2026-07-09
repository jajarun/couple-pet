"""分身梦话 / 出走纸条的 AI 生成。契约同 ai/daily_question.py：无 key 或任何异常都回落本地，永不抛。

这两样都是「每对每天至多一次」的共享资源，**不计入个人 AI 次数上限**（不碰 quota）。
"""

import re

from app.ai.client import chat_completion
from app.ai.prompt import BRANCH_HINT, format_tone, mood_hint
from app.config import settings
from app.rules import dreams

_MAX_LEN = 40  # 梦话/纸条都收成一句话


def _clean(text: str) -> str:
    """把模型输出收成干净的一句话：取首行、去序号/引号、截断。"""
    line = next((ln.strip() for ln in text.splitlines() if ln.strip()), "")
    line = re.sub(r"^\s*\d+[.、)）]\s*", "", line)
    line = re.sub(r"^[-*·]\s*", "", line)
    line = line.strip(" \t　\"'“”‘’「」『』")
    return line[:_MAX_LEN].strip()


def _persona_line(persona: dict, branch: str) -> str:
    tone = format_tone(persona.get("tone", "沙雕"))
    seed = (persona.get("seed") or "").strip()
    seed_line = f"人设：{seed}。" if seed else ""
    form = BRANCH_HINT.get(branch, "")
    return f"你的基调是「{tone}」。{seed_line}{form}"


def _dream_messages(persona: dict, branch: str, stats: dict) -> list[dict]:
    system = (
        "你在扮演一对情侣里、其中一方养的「分身宠物」。现在是深夜，你在说梦话。\n"
        f"{_persona_line(persona, branch)}\n"
        f"此刻状态：{mood_hint(stats)}。\n"
        "只输出梦话本身：一句话、中文口语、不超过 25 字，带点迷糊的睡意，"
        "可以用（括号）描写一个小动作开头。不要引号、不要解释、绝不承认自己是 AI。"
    )
    return [
        {"role": "system", "content": system},
        {"role": "user", "content": "（你睡着了，开始说梦话）"},
    ]


def _note_messages(persona: dict, branch: str) -> list[dict]:
    system = (
        "你在扮演一对情侣里、其中一方养的「分身宠物」。你被冷落、被欺负太久，"
        "赌气离家出走了，走之前留了一张纸条。\n"
        f"{_persona_line(persona, branch)}\n"
        "只输出纸条上的话：一句话、中文口语、不超过 30 字，委屈里带着口是心非，"
        "既想让 TA 后悔、又盼着 TA 来找你。不要引号、不要解释、绝不承认自己是 AI。"
    )
    return [
        {"role": "system", "content": system},
        {"role": "user", "content": "（你抓起笔，在纸上写下）"},
    ]


def generate_dream(persona: dict, branch: str, stats: dict, seed: int) -> tuple[str, bool]:
    """返回 (梦话, used_ai)。无 key 或任何异常都回落本地文案池，永不抛。"""
    if not settings.deepseek_api_key:
        return dreams.pick_dream(branch, seed), False
    try:
        text = _clean(chat_completion(_dream_messages(persona, branch, stats)))
        if not text:
            raise ValueError("empty after clean")
        return text, True
    except Exception:
        return dreams.pick_dream(branch, seed), False


def generate_runaway_note(persona: dict, branch: str, seed: int) -> tuple[str, bool]:
    """返回 (纸条, used_ai)。无 key 或任何异常都回落本地文案池，永不抛。"""
    if not settings.deepseek_api_key:
        return dreams.pick_runaway_note(branch, seed), False
    try:
        text = _clean(chat_completion(_note_messages(persona, branch)))
        if not text:
            raise ValueError("empty after clean")
        return text, True
    except Exception:
        return dreams.pick_runaway_note(branch, seed), False
