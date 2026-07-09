"""纯函数：分身进化树。无 DB / 时钟 / AI / settings。now_iso 一律由调用方传入。

进化只由「饲养者对这只分身做过的动作」驱动（care 累积），**绝不碰 couple 级共享的四个数值**——
否则一对情侣的两只镜像分身会同步长成一模一样。于是：
  我养的那只（代表 TA）长成什么样 = 我怎么对 TA 的；
  TA 养的那只（代表我）长成什么样 = 我在 TA 眼里被养成了什么样。
"""

# 每个阶段的入门 exp：蛋 / 幼体 / 成体 / 完全体
STAGE_THRESHOLDS = [0, 10, 40, 120]
MAX_STAGE = len(STAGE_THRESHOLDS) - 1

# 每个动作值多少经验。不在表里的动作照记进 care，但不涨经验
CARE_WEIGHTS = {
    "poke": 1,
    "scold": 1,
    "chat": 2,
    "miss_you": 2,
    "apologize": 2,
    "feed_dogfood": 3,
    "hug": 3,
    "coax": 3,
}

# 分支归桶（定分支时看各桶占比）；coax（哄）是安抚，归 sweet
BRANCH_BUCKETS = {
    "sweet": ("hug", "miss_you", "apologize", "coax"),
    "glutton": ("feed_dogfood",),
    "dark": ("scold", "poke"),
    "chatty": ("chat",),
}
_BRANCH_ORDER = ("sweet", "glutton", "dark", "chatty")  # 定序 → decide_branch 结果确定，不随 dict 序漂
BALANCED = "balanced"
DOMINANCE = 0.45  # 某桶占比 ≥ 45% 才定型成该分支，否则算均衡

# (stage, branch) → 形态。stage 0/1 还没定型，与 branch 无关
FORMS = {
    (0, ""): {"emoji": "🥚", "title": "一颗蛋"},
    (1, ""): {"emoji": "🐣", "title": "幼体"},
    (2, "sweet"): {"emoji": "🐰", "title": "甜妹雏形"},
    (3, "sweet"): {"emoji": "🦄", "title": "甜心精灵"},
    (2, "glutton"): {"emoji": "🐷", "title": "小猪猪"},
    (3, "glutton"): {"emoji": "🐽", "title": "猪猪本猪"},
    (2, "dark"): {"emoji": "😼", "title": "腹黑体"},
    (3, "dark"): {"emoji": "😈", "title": "黑化完全体"},
    (2, "chatty"): {"emoji": "🐸", "title": "话痨体"},
    (3, "chatty"): {"emoji": "🦜", "title": "复读机精"},
    (2, BALANCED): {"emoji": "🐱", "title": "均衡体"},
    (3, BALANCED): {"emoji": "🐲", "title": "六边形战士"},
}
_DEFAULT_FORM = {"emoji": "👾", "title": "神秘体"}


def empty_state() -> dict:
    return {"stage": 0, "branch": "", "exp": 0, "care": {}, "history": []}


def _normalize(evo) -> dict:
    """容忍 None / {} / 缺键的老数据。不改入参（下游只读或整体复制）。"""
    base = empty_state()
    if evo:
        base.update(evo)
    return base


def record_care(care: dict, action_type: str) -> dict:
    out = dict(care)
    out[action_type] = out.get(action_type, 0) + 1
    return out


def exp_of(care: dict) -> int:
    return sum(CARE_WEIGHTS.get(action, 0) * n for action, n in care.items())


def stage_of(exp: int) -> int:
    stage = 0
    for i, threshold in enumerate(STAGE_THRESHOLDS):
        if exp >= threshold:
            stage = i
    return stage


def decide_branch(care: dict) -> str:
    """按桶占比定分支。空 care / 平局 / 占比不够 DOMINANCE → balanced。"""
    sums = {b: sum(care.get(a, 0) for a in actions) for b, actions in BRANCH_BUCKETS.items()}
    grand = sum(sums.values())
    if grand == 0:
        return BALANCED
    top = max(sums.values())
    winners = [b for b in _BRANCH_ORDER if sums[b] == top]
    if len(winners) != 1:
        return BALANCED
    return winners[0] if top / grand >= DOMINANCE else BALANCED


def evolve(evo: dict, action_type: str, now_iso: str) -> tuple[dict, bool]:
    """记一次饲养动作，重算 exp/stage，必要时定型分支。返回 (新 evo, 是否刚进化)。不改入参。

    分支在**首次进入成体（stage 2）那一刻**按 care 占比定型，此后不可逆——
    「你把它养歪了就是养歪了」，这是进化树的分量所在。
    """
    cur = _normalize(evo)
    care = record_care(cur["care"], action_type)
    exp = exp_of(care)
    new_stage = stage_of(exp)
    branch = cur["branch"]
    if new_stage >= 2 and not branch:
        branch = decide_branch(care)
    evolved = new_stage > cur["stage"]
    history = cur["history"]
    if evolved:
        history = history + [{"stage": new_stage, "branch": branch, "at": now_iso}]
    return {"stage": new_stage, "branch": branch, "exp": exp, "care": care, "history": history}, evolved


def view(evo: dict) -> dict:
    """读时派生（不改存储）。use_form_emoji=False 时前端应优先用用户捏的 appearance.emoji。"""
    e = _normalize(evo)
    stage, exp = e["stage"], e["exp"]
    branch = e["branch"] or (BALANCED if stage >= 2 else "")
    current = STAGE_THRESHOLDS[stage]
    if stage < MAX_STAGE:
        next_exp = STAGE_THRESHOLDS[stage + 1]
        progress = round((exp - current) / (next_exp - current), 3)
    else:
        next_exp, progress = None, 1.0
    form = FORMS.get((stage, branch)) or FORMS.get((stage, "")) or _DEFAULT_FORM
    return {
        "stage": stage,
        "branch": branch,
        "exp": exp,
        "next_exp": next_exp,
        "progress": progress,
        "emoji": form["emoji"],
        "title": form["title"],
        "use_form_emoji": stage >= 2,
    }
