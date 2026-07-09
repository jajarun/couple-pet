"""纯函数：把人设 + 数值心情 + 动作 + 最近对话拼成 DeepSeek messages。无网络/DB/时钟。"""

_RULES = (
    "无厘头、沙雕、始终在角色里，绝不承认自己是 AI，绝不长篇大论，"
    "回应控制在 1-3 句，中文口语。"
)


def mood_hint(stats: dict) -> str:
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


def format_tone(tone) -> str:
    """把基调归一成一句可读文案：list 用顿号拼、str 原样、空值回落「沙雕」。
    基调支持多选(存成数组)后,老数据仍是字符串,这里统一兼容。"""
    if isinstance(tone, list):
        parts = [str(t).strip() for t in tone if str(t).strip()]
        return "、".join(parts) if parts else "沙雕"
    tone = (str(tone).strip() if tone is not None else "")
    return tone or "沙雕"


def _gender_hint(persona: dict) -> str:
    gender = persona.get("gender")
    if gender == "male":
        return "你是个男生，用男生的口吻说话。\n"
    if gender == "female":
        return "你是个女生，用女生的口吻说话。\n"
    return ""


# 进化形态反过来改写说话方式：饲养者怎么对它，它就长成什么样、就怎么回嘴。
# 只有成体（stage>=2，分支已定型）才注入，调用方负责在没定型时传空。
BRANCH_HINT = {
    "sweet": "你已进化成甜妹形态，说话甜、黏人、爱撒娇。",
    "glutton": "你已进化成猪猪形态，满脑子吃的，回话常含混着想吃东西。",
    "dark": "你已黑化，说话毒舌、腹黑、带刺，刀子嘴豆腐心。",
    "chatty": "你已进化成话痨形态，话密、爱接梗、停不下来。",
    "balanced": "你是均衡形态，情绪稳定，什么都来一点。",
}


def _branch_hint(persona: dict) -> str:
    hint = BRANCH_HINT.get(persona.get("branch") or "")
    return f"{hint}\n" if hint else ""


def _system_prompt(persona: dict, stats: dict) -> str:
    tone = format_tone(persona.get("tone", "沙雕"))
    seed = (persona.get("seed") or "").strip()
    seed_line = seed if seed else "（对方还没细说，你自己发挥）"
    return (
        "你在扮演对方养的「分身宠物」——代表 TA 眼里的另一半。\n"
        f"你的基调是「{tone}」。人设：{seed_line}。\n"
        f"{_gender_hint(persona)}"
        f"{_branch_hint(persona)}"
        f"规则：{_RULES}\n"
        f"此刻状态：{mood_hint(stats)}。"
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
    if action_type == "nudge":
        final = (
            "（对方安静了一会儿，没搭理你。你主动开口——撩TA、或找个由头勾TA过来陪你互动，"
            "结合你此刻的心情，就一句话，别承认自己是 AI）"
        )
    elif action_type == "scold":
        final = f"（对方在骂你）{content}"
    else:
        final = content
    messages.append({"role": "user", "content": final})
    return messages
