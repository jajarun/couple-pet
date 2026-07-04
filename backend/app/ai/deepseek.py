"""DeepSeek 分身反应：编排 prompt + 调用 + 兜底。返回 (文本, used_ai)，永不抛。"""

from app.ai.client import AIError, chat_completion
from app.ai.prompt import build_messages
from app.config import settings


def _fallback(persona: dict, action_type: str, content: str) -> str:
    """tone-aware 本地兜底（无 key / 出错时用）。含 persona.tone 与内容回显。"""
    tone = persona.get("tone", "沙雕")
    said = content.strip() if content else ""
    tail = f"「{said}」" if said else ""
    return f"[{tone}分身] 收到你的 {action_type}{tail}，哼，本尊可不吃这套~"


def generate_reaction(
    persona: dict,
    stats: dict,
    action_type: str,
    content: str,
    recent: list[dict],
    memory_summary: str = "",  # 本计划恒为 ""，保留向前兼容
) -> tuple[str, bool]:
    if not settings.deepseek_api_key:
        return _fallback(persona, action_type, content), False
    try:
        messages = build_messages(persona, stats, action_type, content, recent)
        return chat_completion(messages), True
    except Exception:
        return _fallback(persona, action_type, content), False
