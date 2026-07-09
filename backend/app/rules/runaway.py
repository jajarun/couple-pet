"""纯函数：分身离家出走的判据。无 DB / 时钟（时间窗过滤在 service 层做）。

**故意不看 couple 级共享的 grievance**，两个原因：
1. grievance 每小时自愈 −2（stats.TIME_DELTA_PER_HOUR），满值 100 也只撑 10 小时——
   「委屈≥80 且 N 小时没安抚」在 N 大一点时根本不可能同时成立。
2. grievance 是两人共享的，拿它当判据会让两只镜像分身同时出走。

改成只看「**这个饲养者自己**在最近一个窗口里怎么对这只分身」：
你在 6 小时里骂了它 5 次、一次都没哄，它就跑了。谁欺负谁的分身，谁的跑。
"""

HOSTILE = ("scold", "poke")
SOOTHE = ("feed_dogfood", "hug", "apologize", "coax")

WINDOW_HOURS = 6  # 只看最近这么久的动作
HOSTILE_THRESHOLD = 5  # 窗口内敌意动作攒到这个数就跑


def should_run_away(hostile_count: int, soothe_count: int, already_away: bool) -> bool:
    """窗口内敌意动作够多、且一次都没安抚过，且它还没跑 → 跑。"""
    if already_away:
        return False
    if soothe_count > 0:  # 哄过一次就既往不咎
        return False
    return hostile_count >= HOSTILE_THRESHOLD


def is_away(last_runaway_id: int | None, last_coax_id: int | None) -> bool:
    """出走态纯从事件流派生：最后一条 runaway 比最后一条 coax 新 → 它还在外面。

    两者的 actor 都记成 keeper，所以同一把钥匙就能配对，两只分身天然隔离。
    """
    if last_runaway_id is None:
        return False
    return last_coax_id is None or last_runaway_id > last_coax_id
