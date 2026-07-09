"""纯函数：分身离家出走的判据 + 出走三态。无 DB / 时钟（时间窗过滤在 service 层做）。

**故意不看 couple 级共享的 grievance**，两个原因：
1. grievance 每小时自愈 −2（stats.TIME_DELTA_PER_HOUR），满值 100 也只撑 10 小时——
   「委屈≥80 且 N 小时没安抚」在 N 大一点时根本不可能同时成立。
2. grievance 是两人共享的，拿它当判据会让两只镜像分身同时出走。

改成只看「**这个饲养者自己**在最近一个窗口里怎么对这只分身」：
你在 1 小时里骂满 5 次、一次都没哄，**第 5 次骂落下的那一刻**它就跑。谁欺负谁的分身，谁的跑。
"""

# 只有「骂」算数。**戳不算**——首页点一下分身发的就是 poke，手滑五下不该把它逼走。
HOSTILE = ("scold",)
SOOTHE = ("feed_dogfood", "hug", "apologize", "coax")

WINDOW_HOURS = 1  # 只看最近这么久的动作
HOSTILE_THRESHOLD = 5  # 窗口内骂满这个数就跑。满了当场就跑，不等定时任务

# 三态。跑了 --coax--> 等对方点头 --forgive--> 回家
HOME = "home"
AWAY = "away"  # 跑了，还没人来哄
PENDING = "pending"  # 哄过了，就差它代表的那个人点头


def should_run_away(hostile_count: int, soothe_count: int) -> bool:
    """窗口内骂够了、且一次都没安抚过 → 跑。

    调用方保证它此刻在家（跑在外面时除了「哄」什么都发不出来，压根攒不出敌意）。
    """
    if soothe_count > 0:  # 哄过一次就既往不咎
        return False
    return hostile_count >= HOSTILE_THRESHOLD


def state_of(
    last_runaway_id: int | None, last_coax_id: int | None, last_forgive_id: int | None
) -> str:
    """出走态纯从事件流派生：三个标记里谁的 id 最新，谁说了算。

    三者的 actor 都记成 keeper，所以同一把钥匙就能配对，两只分身天然隔离。
    """
    if last_runaway_id is None:
        return HOME  # 从没跑过
    if last_forgive_id is not None and last_forgive_id > last_runaway_id:
        return HOME  # 跑过，被原谅了
    if last_coax_id is not None and last_coax_id > last_runaway_id:
        return PENDING  # 哄过了，等对方点头
    return AWAY
