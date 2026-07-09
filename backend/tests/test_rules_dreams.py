import pytest

from app.rules.dreams import (
    LOCAL_DREAMS,
    LOCAL_RUNAWAY_NOTES,
    pick_dream,
    pick_runaway_note,
)
from app.rules.evolution import BALANCED, BRANCH_BUCKETS


@pytest.mark.parametrize("pool", [LOCAL_DREAMS, LOCAL_RUNAWAY_NOTES])
def test_every_branch_has_its_own_lines(pool):
    for branch in (*BRANCH_BUCKETS, BALANCED):
        lines = pool[branch]
        assert len(lines) >= 3, f"{branch} 只有 {len(lines)} 条"
        assert len(set(lines)) == len(lines), f"{branch} 有重复"


def test_picks_from_the_matching_branch():
    assert pick_dream("glutton", 0) in LOCAL_DREAMS["glutton"]
    assert pick_runaway_note("dark", 0) in LOCAL_RUNAWAY_NOTES["dark"]


def test_same_seed_same_line():
    assert pick_dream("dark", 7) == pick_dream("dark", 7)


def test_seed_walks_the_pool():
    picked = {pick_dream("sweet", i) for i in range(len(LOCAL_DREAMS["sweet"]))}
    assert picked == set(LOCAL_DREAMS["sweet"])


def test_unformed_and_unknown_branches_fall_back_to_balanced():
    # 没到成体时 branch 是 ""；老数据/手改库也可能给个不认识的值
    for branch in ("", "nonsense"):
        assert pick_dream(branch, 3) in LOCAL_DREAMS[BALANCED]
        assert pick_runaway_note(branch, 3) in LOCAL_RUNAWAY_NOTES[BALANCED]
