"""剧情副本的 AI 生成：开场 / 续写 / 结局。

契约同 ai/daily_question.py、ai/dream.py：**无 key、任何异常、格式解析失败，一律回落本地剧本，
永不抛**。剧情是「每对每天一章」的共享资源，**不计入个人 AI 次数上限**（全程不碰 quota）。

跟别处不一样的两点：
1. 要的不是一句话，而是「场景 + 2~3 个选项」的结构化输出 → 严格格式 + 正则解析，解析不出来就当失败。
2. 因此必须给 chat_completion 传 per-call 的 max_tokens / temperature——默认的 200 token 会把
   故事拦腰截断，1.3 的 temperature 会把格式写崩。
"""

import re

from app.ai.client import chat_completion
from app.config import settings
from app.rules import stories

STORY_MAX_TOKENS = 500  # 默认 200 太短，故事会被截断
STORY_TEMPERATURE = 0.9  # 默认 1.3 太飘，严格格式会写崩

_MAX_TITLE = 24
_MAX_SCENE = 160
_MAX_OPTION = 24
_MIN_OPTIONS = 2
_MAX_OPTIONS = 3

_TITLE_RE = re.compile(r"^\s*标题[：:]\s*(.+)$")
_SCENE_RE = re.compile(r"^\s*场景[：:]\s*(.*)$")
_OPTION_RE = re.compile(r"^\s*[A-Ca-c][.、)）]\s*(.+)$")


def _trim(s: str, limit: int) -> str:
    return s.strip(" \t　\"'“”‘’「」『』").strip()[:limit].strip()


def _parse(text: str, *, want_title: bool, want_options: bool) -> tuple[str, str, list[str]]:
    """把「标题：… / 场景：…（可跨行）/ A. … B. …」拆出来。任一必需段缺失即 ValueError。"""
    lines = text.splitlines()

    title = ""
    if want_title:
        m = next((_TITLE_RE.match(ln) for ln in lines if _TITLE_RE.match(ln)), None)
        if m is None:
            raise ValueError("no title")
        title = _trim(m.group(1), _MAX_TITLE)
        if not title:
            raise ValueError("empty title")

    scene_at = next((i for i, ln in enumerate(lines) if _SCENE_RE.match(ln)), None)
    if scene_at is None:
        raise ValueError("no scene")
    chunk = [_SCENE_RE.match(lines[scene_at]).group(1)]
    for ln in lines[scene_at + 1 :]:  # 场景可能跨行，收到第一个选项行为止
        if _OPTION_RE.match(ln) or _TITLE_RE.match(ln):
            break
        chunk.append(ln)
    scene = _trim(" ".join(x.strip() for x in chunk if x.strip()), _MAX_SCENE)
    if not scene:
        raise ValueError("empty scene")

    options: list[str] = []
    if want_options:
        for ln in lines:
            m = _OPTION_RE.match(ln)
            if m:
                opt = _trim(m.group(1), _MAX_OPTION)
                if opt and opt not in options:
                    options.append(opt)
        if not _MIN_OPTIONS <= len(options) <= _MAX_OPTIONS:
            raise ValueError(f"got {len(options)} options")

    return title, scene, options


def _echo(choices: list[tuple[str, str]]) -> str:
    """把两个人刚才的选择回显成一句话。

    场景是**存一份、两个人共读**的，所以只能用昵称，不能写「你 / TA」。
    """
    if not choices:
        return ""
    texts = {t for _n, t in choices}
    if len(texts) == 1:
        return f"你们俩都选了「{choices[0][1]}」。"
    return "，".join(f"{n}选了「{t}」" for n, t in choices) + "。"


def _players_line(players: list[dict]) -> str:
    bits = []
    for p in players:
        nick = p.get("nickname") or "TA"
        gender = {"male": "男", "female": "女"}.get(p.get("gender") or "", "")
        tag = p.get("pet_title") or ""
        tone = p.get("tone") or ""
        extra = "、".join(x for x in (gender, tone, tag) if x)
        bits.append(f"{nick}（{extra}）" if extra else nick)
    return " 和 ".join(bits)


_FORMAT = (
    "严格按下面的格式输出，不要任何多余的话：\n"
    "场景：<1~3 句，不超过 60 字>\n"
    "A. <选项，不超过 12 字>\n"
    "B. <选项，不超过 12 字>\n"
    "C. <选项，不超过 12 字>"
)


def _system(players: list[dict]) -> str:
    return (
        f"你在给一对情侣写一段互动小剧情。主角是 {_players_line(players)}。\n"
        "文风：中文口语、有画面感、带点少女漫的甜和一点无厘头，别煽情、别说教。\n"
        "剧情里不要出现「玩家」「选项」「AI」这类词，就当是在写他们俩真实发生的事。"
    )


def _opening_messages(players: list[dict]) -> list[dict]:
    return [
        {"role": "system", "content": _system(players)},
        {
            "role": "user",
            "content": (
                "开一段全新的小剧情：给它起个名字，写第一幕，再给两个人三个可选的行动。\n"
                "严格按下面的格式输出，不要任何多余的话：\n"
                "标题：<不超过 10 字>\n"
                "场景：<1~3 句，不超过 60 字>\n"
                "A. <选项，不超过 12 字>\nB. <选项，不超过 12 字>\nC. <选项，不超过 12 字>"
            ),
        },
    ]


def _history_block(title: str, history: list[str]) -> str:
    so_far = "\n".join(f"{i + 1}. {s}" for i, s in enumerate(history))
    return f"剧情《{title}》已经发生的：\n{so_far}"


def _continuation_messages(
    title: str, history: list[str], choices: list[tuple[str, str]], players: list[dict]
) -> list[dict]:
    picked = "；".join(f"{n} 选了「{t}」" for n, t in choices)
    return [
        {"role": "system", "content": _system(players)},
        {
            "role": "user",
            "content": (
                f"{_history_block(title, history)}\n\n"
                f"刚才这一幕，两个人各自做了选择：{picked}。\n"
                "把**两个人的选择**同时写进后果里（谁的选择带来了什么），"
                f"然后推进到下一幕，再给三个新选项。\n{_FORMAT}"
            ),
        },
    ]


def _ending_messages(
    title: str, history: list[str], choices: list[tuple[str, str]], players: list[dict]
) -> list[dict]:
    picked = "；".join(f"{n} 选了「{t}」" for n, t in choices)
    return [
        {"role": "system", "content": _system(players)},
        {
            "role": "user",
            "content": (
                f"{_history_block(title, history)}\n\n"
                f"最后一幕，两个人各自做了选择：{picked}。\n"
                "写出结局：收束这两个选择，给他们俩一个温柔又有点好笑的收尾，"
                "最后一句要让人想收藏。\n"
                "严格按下面的格式输出，不要任何多余的话：\n"
                "场景：<2~4 句，不超过 80 字>"
            ),
        },
    ]


def _ask(messages: list[dict], *, want_title: bool, want_options: bool):
    text = chat_completion(
        messages, max_tokens=STORY_MAX_TOKENS, temperature=STORY_TEMPERATURE
    )
    return _parse(text, want_title=want_title, want_options=want_options)


def generate_opening(players: list[dict], seed: int) -> tuple[str, str, list[str], bool]:
    """返回 (标题, 第一幕, 选项, used_ai)。无 key / 异常 / 解析失败都回落本地剧本，永不抛。"""
    if settings.deepseek_api_key:
        try:
            title, scene, options = _ask(
                _opening_messages(players), want_title=True, want_options=True
            )
            return title, scene, options, True
        except Exception:
            pass
    story = stories.pick_story(seed)
    first = stories.local_round(story, 1)
    return story["title"], first["scene"], first["options"], False


def generate_continuation(
    title: str,
    history: list[str],
    choices: list[tuple[str, str]],
    round_no: int,
    players: list[dict],
    seed: int,
) -> tuple[str, list[str], bool]:
    """写出两个选择的共同后果 + 下一幕的新选项。round_no 是**新的那一幕**的序号。"""
    if settings.deepseek_api_key:
        try:
            _t, scene, options = _ask(
                _continuation_messages(title, history, choices, players),
                want_title=False,
                want_options=True,
            )
            return scene, options, True
        except Exception:
            pass
    # 本地剧本是线性的（选项不改走向），所以把两人的选择回显在开头，否则读起来像没人在听
    story = stories.pick_story(seed)
    nxt = stories.local_round(story, round_no)
    return f"{_echo(choices)}{nxt['scene']}", nxt["options"], False


def generate_ending(
    title: str,
    history: list[str],
    choices: list[tuple[str, str]],
    players: list[dict],
    seed: int,
) -> tuple[str, bool]:
    """收束成结局。结局幕没有选项。"""
    if settings.deepseek_api_key:
        try:
            _t, scene, _o = _ask(
                _ending_messages(title, history, choices, players),
                want_title=False,
                want_options=False,
            )
            return scene, True
        except Exception:
            pass
    story = stories.pick_story(seed)
    return f"{_echo(choices)}{stories.local_ending(story)}", False
