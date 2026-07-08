from app.ai.prompt import build_messages, _mood_hint

LOW = {"grievance": 0, "dogfood": 0, "miss": 0, "intimacy": 0}


def test_system_carries_tone_and_seed():
    msgs = build_messages(
        {"tone": "毒舌", "seed": "爱吃醋的小恶魔"}, LOW, "chat", "在吗", []
    )
    sys = msgs[0]
    assert sys["role"] == "system"
    assert "毒舌" in sys["content"]
    assert "爱吃醋的小恶魔" in sys["content"]


def test_multi_tone_joined_without_brackets():
    # 基调多选(数组)→ 顿号拼接进 prompt,不能是 ['毒舌','高冷'] 的 list repr
    msgs = build_messages({"tone": ["毒舌", "高冷"]}, LOW, "chat", "在吗", [])
    content = msgs[0]["content"]
    assert "毒舌" in content and "高冷" in content
    assert "毒舌、高冷" in content
    assert "[" not in content and "'" not in content


def test_scold_final_turn_marks_being_scolded():
    msgs = build_messages({"tone": "毒舌"}, LOW, "scold", "大猪蹄子", [])
    last = msgs[-1]
    assert last["role"] == "user"
    assert "大猪蹄子" in last["content"]
    assert "骂" in last["content"]


def test_chat_final_turn_is_raw_content():
    msgs = build_messages({"tone": "憨憨"}, LOW, "chat", "在吗", [])
    assert msgs[-1] == {"role": "user", "content": "在吗"}


def test_recent_renders_as_alternating_turns():
    recent = [
        {"speaker": "对方", "text": "你好"},
        {"speaker": "分身", "text": "哼"},
    ]
    msgs = build_messages({"tone": "毒舌"}, LOW, "chat", "在吗", recent)
    assert msgs[1] == {"role": "user", "content": "你好"}
    assert msgs[2] == {"role": "assistant", "content": "哼"}
    assert msgs[-1]["content"] == "在吗"


def test_missing_seed_still_builds_system():
    msgs = build_messages({"tone": "高冷"}, LOW, "chat", "hi", [])
    assert "高冷" in msgs[0]["content"]


def test_gender_hint_present_when_set():
    male = build_messages({"tone": "毒舌", "gender": "male"}, LOW, "chat", "hi", [])
    assert "男生" in male[0]["content"]
    female = build_messages({"tone": "毒舌", "gender": "female"}, LOW, "chat", "hi", [])
    assert "女生" in female[0]["content"]


def test_gender_hint_absent_when_unset():
    msgs = build_messages({"tone": "毒舌"}, LOW, "chat", "hi", [])
    assert "男生" not in msgs[0]["content"] and "女生" not in msgs[0]["content"]


def test_mood_hint_reflects_high_grievance():
    assert "委屈" in _mood_hint({"grievance": 70, "dogfood": 0, "miss": 0, "intimacy": 0})


def test_mood_hint_default_when_all_low():
    assert _mood_hint(LOW) == "你心情平常"
