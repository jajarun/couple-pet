"""纯函数：把人设 + 数值心情 + 动作 + 最近对话拼成 DeepSeek messages。无网络/DB/时钟。"""

_RULES = (
    "无厘头、沙雕、始终在角色里，绝不承认自己是 AI，绝不长篇大论，"
    "回应控制在 1-3 句，中文口语。"
)


def _mood_hint(stats: dict) -> str:
    hints = []
    if stats.get("grievance", 0) >= 60:
        hints.append("你此刻有点委屈、带刺，想被哄")
    if stats.get("miss", 0) >= 60:
        hints.append("你很想念对方")
    if stats.get("intimacy", 0) >= 60:
        hints.append("你和对方很亲密、黏人")
    if stats.get("dogfood", 0) >= 60:
        hints.append("你刚被喂饱，满足慵懒")
    return "；".join(hints) if hints else "你心情平常"


def _system_prompt(persona: dict, stats: dict) -> str:
    tone = persona.get("tone", "沙雕")
    seed = (persona.get("seed") or "").strip()
    seed_line = seed if seed else "（对方还没细说，你自己发挥）"
    return (
        "你在扮演对方养的「分身宠物」——代表 TA 眼里的另一半。\n"
        f"你的基调是「{tone}」。人设：{seed_line}。\n"
        f"规则：{_RULES}\n"
        f"此刻状态：{_mood_hint(stats)}。"
    )


def build_messages(
    persona: dict,
    stats: dict,
    action_type: str,
    content: str,
    recent: list[dict],
) -> list[dict]:
    messages = [{"role": "system", "content": _system_prompt(persona, stats)}]
    for turn in recent:
        role = "user" if turn.get("speaker") == "对方" else "assistant"
        messages.append({"role": role, "content": turn.get("text", "")})
    final = f"（对方在骂你）{content}" if action_type == "scold" else content
    messages.append({"role": "user", "content": final})
    return messages
