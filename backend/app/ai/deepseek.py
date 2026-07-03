"""DeepSeek 分身反应。本版为确定性 Stub，不联网；真实实现后置替换。"""


def generate_reaction(
    persona: dict,
    stats: dict,
    action_type: str,
    content: str,
    memory_summary: str = "",
) -> str:
    tone = persona.get("tone", "沙雕")
    said = content.strip() if content else ""
    tail = f"「{said}」" if said else ""
    return f"[{tone}分身] 收到你的 {action_type}{tail}，哼，本尊可不吃这套~"
