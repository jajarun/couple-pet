import app.ai.story as story_mod
from app.ai.story import (
    STORY_MAX_TOKENS,
    STORY_TEMPERATURE,
    generate_continuation,
    generate_ending,
    generate_opening,
)
from app.config import settings
from app.rules import stories

PLAYERS = [
    {"id": 1, "nickname": "小明", "gender": "male", "pet_title": "腹黑体", "tone": "毒舌"},
    {"id": 2, "nickname": "小红", "gender": "female", "pet_title": "", "tone": "沙雕"},
]
PICKED = [("小明", "疯狂按每一个按钮"), ("小红", "先按下紧急呼叫铃")]

GOOD_OPENING = """标题：困在电梯里
场景：叮——灯灭了。电梯卡在两层之间。
A. 疯狂按按钮
B. 按紧急呼叫铃
C. 讲个冷笑话"""

GOOD_CONTINUATION = """场景：你按遍了所有按钮，她按下了呼叫铃。
对讲机里传来一句「等着」。
A. 坐到地上
B. 翻包找吃的
C. 打开手电筒"""


def _stub(monkeypatch, text):
    seen = {}

    def fake(messages, **kw):
        seen["messages"] = messages
        seen.update(kw)
        return text

    monkeypatch.setattr(story_mod, "chat_completion", fake)
    monkeypatch.setattr(story_mod.settings, "deepseek_api_key", "sk-x")
    return seen


# ---------- 无 key / 失败 / 解析不出来，一律回落本地剧本 ----------

def test_no_key_falls_back_to_the_local_script(monkeypatch):
    monkeypatch.setattr(story_mod.settings, "deepseek_api_key", "")
    title, scene, options, used_ai = generate_opening(PLAYERS, 0)
    local = stories.pick_story(0)
    assert used_ai is False
    assert title == local["title"]
    assert scene == local["rounds"][0]["scene"]
    assert options == local["rounds"][0]["options"]


def test_ai_blowing_up_falls_back_and_never_raises(monkeypatch):
    _stub(monkeypatch, "")
    monkeypatch.setattr(
        story_mod, "chat_completion", lambda *a, **k: (_ for _ in ()).throw(RuntimeError("boom"))
    )
    _t, _s, options, used_ai = generate_opening(PLAYERS, 1)
    assert used_ai is False
    assert options == stories.pick_story(1)["rounds"][0]["options"]


def test_unparseable_prose_falls_back(monkeypatch):
    """AI 回了一坨散文、没按格式 → 当失败处理，别把散文当场景塞进库。"""
    _stub(monkeypatch, "从前有座山，山里有座庙，庙里有两个人被困住了。")
    _t, scene, options, used_ai = generate_opening(PLAYERS, 2)
    assert used_ai is False
    assert scene == stories.pick_story(2)["rounds"][0]["scene"]
    assert len(options) >= 2


def test_too_few_options_falls_back(monkeypatch):
    _stub(monkeypatch, "标题：X\n场景：只有一条路。\nA. 走")
    _t, _s, _o, used_ai = generate_opening(PLAYERS, 3)
    assert used_ai is False


def test_a_missing_title_falls_back(monkeypatch):
    _stub(monkeypatch, "场景：门开了。\nA. 进\nB. 不进")
    _t, _s, _o, used_ai = generate_opening(PLAYERS, 0)
    assert used_ai is False


# ---------- 解析成功的路径 ----------

def test_opening_parses_title_scene_and_options(monkeypatch):
    _stub(monkeypatch, GOOD_OPENING)
    title, scene, options, used_ai = generate_opening(PLAYERS, 0)
    assert used_ai is True
    assert title == "困在电梯里"
    assert scene == "叮——灯灭了。电梯卡在两层之间。"
    assert options == ["疯狂按按钮", "按紧急呼叫铃", "讲个冷笑话"]


def test_a_multiline_scene_is_folded_into_one(monkeypatch):
    _stub(monkeypatch, GOOD_CONTINUATION)
    scene, options, used_ai = generate_continuation("困在电梯里", ["第一幕"], PICKED, 2, PLAYERS, 0)
    assert used_ai is True
    assert scene == "你按遍了所有按钮，她按下了呼叫铃。 对讲机里传来一句「等着」。"
    assert len(options) == 3


def test_the_ending_has_no_options(monkeypatch):
    _stub(monkeypatch, "场景：门开了，检修师傅探头进来。你俩还在笑。")
    scene, used_ai = generate_ending("困在电梯里", ["第一幕"], PICKED, PLAYERS, 0)
    assert used_ai is True
    assert scene.startswith("门开了")


def test_story_calls_ask_for_room_and_a_steady_hand(monkeypatch):
    """默认的 200 token 会把故事截断、1.3 的温度会把格式写崩，必须 per-call 覆盖。"""
    seen = _stub(monkeypatch, GOOD_OPENING)
    generate_opening(PLAYERS, 0)
    assert seen["max_tokens"] == STORY_MAX_TOKENS > settings.deepseek_max_tokens
    assert seen["temperature"] == STORY_TEMPERATURE < settings.deepseek_temperature


def test_prompt_carries_both_nicknames_and_the_evolved_form(monkeypatch):
    seen = _stub(monkeypatch, GOOD_OPENING)
    generate_opening(PLAYERS, 0)
    system = seen["messages"][0]["content"]
    assert "小明" in system and "小红" in system
    assert "腹黑体" in system  # 被养成什么样，故事里就是什么样
    assert "毒舌" in system


def test_continuation_prompt_names_both_choices(monkeypatch):
    seen = _stub(monkeypatch, GOOD_CONTINUATION)
    generate_continuation("困在电梯里", ["第一幕"], PICKED, 2, PLAYERS, 0)
    user = seen["messages"][1]["content"]
    assert "疯狂按每一个按钮" in user and "先按下紧急呼叫铃" in user
    assert "第一幕" in user  # 前情提要也带上


# ---------- 本地兜底必须回显两人的选择，否则读起来像没人在听 ----------

def test_local_continuation_echoes_both_choices(monkeypatch):
    monkeypatch.setattr(story_mod.settings, "deepseek_api_key", "")
    scene, options, used_ai = generate_continuation("x", [], PICKED, 2, PLAYERS, 0)
    assert used_ai is False
    assert "小明选了「疯狂按每一个按钮」" in scene
    assert "小红选了「先按下紧急呼叫铃」" in scene
    assert scene.endswith(stories.pick_story(0)["rounds"][1]["scene"])
    assert options == stories.pick_story(0)["rounds"][1]["options"]


def test_local_echo_collapses_when_you_both_picked_the_same_thing(monkeypatch):
    monkeypatch.setattr(story_mod.settings, "deepseek_api_key", "")
    same = [("小明", "坐到地上"), ("小红", "坐到地上")]
    scene, _o, _u = generate_continuation("x", [], same, 2, PLAYERS, 0)
    assert scene.startswith("你们俩都选了「坐到地上」。")


def test_the_echo_never_says_you_or_ta(monkeypatch):
    """场景是**存一份、两个人共读**的，用「你/TA」会有一个人读反。"""
    monkeypatch.setattr(story_mod.settings, "deepseek_api_key", "")
    scene, _o, _u = generate_continuation("x", [], PICKED, 2, PLAYERS, 0)
    head = scene.split("。")[0]
    assert "TA" not in head


def test_local_ending_echoes_too(monkeypatch):
    monkeypatch.setattr(story_mod.settings, "deepseek_api_key", "")
    scene, used_ai = generate_ending("x", [], PICKED, PLAYERS, 0)
    assert used_ai is False
    assert "小明选了" in scene
    assert scene.endswith(stories.local_ending(stories.pick_story(0)))


# ---------- 剧情是情侣级共享资源，绝不吃个人 AI 额度 ----------

def test_stories_never_touch_personal_quota():
    for name in ("quota", "record_ai_usage", "ai_quota_available"):
        assert not hasattr(story_mod, name), f"ai/story.py 不该碰 {name}"
