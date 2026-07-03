"""纯函数：互动动作对共享数值的影响。无 DB / 时钟 / AI / config 依赖。"""

import random

from app.rules.stats import clamp

ACTION_TYPES = ["scold", "poke", "feed_dogfood", "hug", "miss_you", "apologize", "chat"]

# 需要叫 DeepSeek 的动作（骂 / 聊天）；其余走本地模板
AI_ACTIONS = {"scold", "chat"}

# 每个动作对数值的增量（未列出的键不变）
ACTION_EFFECTS = {
    "scold": {"grievance": 15},
    "poke": {"grievance": 5},
    "feed_dogfood": {"dogfood": 20, "grievance": -10},
    "hug": {"miss": -30, "intimacy": 10},
    "miss_you": {"miss": -20, "intimacy": 6},
    "apologize": {"grievance": -25, "intimacy": 8},
    "chat": {},
}

# 便宜动作的本地沙雕文案（不烧 API），随机挑一句
LOCAL_REACTIONS = {
    "poke": ["戳你咋了，我这叫亲密接触。", "再戳我可要收费了啊喂。"],
    "feed_dogfood": ["狗粮已入库，本汪原地满血复活。", "这波狗粮我先干为敬。"],
    "hug": ["抱一下，续命一整天。", "行吧行吧，勉强让你抱三秒。"],
    "miss_you": ["想我啦？我可是一直在你脑子里蹦迪。", "别想了，我这不就来了。"],
    "apologize": ["哼，看在你态度诚恳的份上，本尊原谅你了。", "算了算了，谁让我大度呢。"],
}


def apply_action(stats: dict, action: str) -> tuple[dict, bool, str | None]:
    if action not in ACTION_EFFECTS:
        raise ValueError(f"unknown action: {action}")
    out = dict(stats)
    for key, delta in ACTION_EFFECTS[action].items():
        out[key] = clamp(stats[key] + delta)
    needs_ai = action in AI_ACTIONS
    reaction = None if needs_ai else random.choice(LOCAL_REACTIONS[action])
    return out, needs_ai, reaction
