"""Web Push 发送编排。契约同 ai/deepseek.py：绝不因推送失败而影响主流程、永不抛。

- 无 VAPID 私钥 = 关闭推送，直接 no-op（dev/CI 离线兜底，同 deepseek_api_key 范式）。
- 发送失败：404/410（订阅已失效）→ 删库；其余异常吞掉记日志。
- 自开 SessionLocal：供 BackgroundTasks 与定时 job 复用，不依赖请求作用域会话
  （挂点务必在 commit 前把 partner_id 这类值取成普通 int 再入队，别把 ORM 对象丢进后台任务）。
"""

import json
import logging

from pywebpush import WebPushException, webpush

from app.config import settings
from app.db import SessionLocal
from app.models import PushSubscription

logger = logging.getLogger(__name__)


def partner_of(couple, user_id: int) -> int | None:
    """couple 里 user_id 的另一半（未配对时另一半可能为 None）。挂点在 commit 前同步调用取 int。"""
    return couple.user_b_id if couple.user_a_id == user_id else couple.user_a_id


def send_to_user(user_id: int, payload: dict) -> None:
    """给某 user 的所有订阅发 Web Push。无私钥则 no-op；失效订阅顺手删。永不抛。"""
    if not settings.vapid_private_key:
        return
    db = SessionLocal()
    try:
        subs = (
            db.query(PushSubscription).filter(PushSubscription.user_id == user_id).all()
        )
        data = json.dumps(payload, ensure_ascii=False)
        for sub in subs:
            try:
                webpush(
                    subscription_info={
                        "endpoint": sub.endpoint,
                        "keys": {"p256dh": sub.p256dh, "auth": sub.auth},
                    },
                    data=data,
                    vapid_private_key=settings.vapid_private_key,
                    vapid_claims={"sub": settings.vapid_subject},
                )
            except WebPushException as e:
                code = getattr(getattr(e, "response", None), "status_code", None)
                if code in (404, 410):  # 订阅失效 → 删
                    db.delete(sub)
                else:
                    logger.warning("web push failed (user=%s): %s", user_id, e)
            except Exception as e:  # 任何其它异常都不许冒泡
                logger.warning("web push error (user=%s): %s", user_id, e)
        db.commit()
    except Exception as e:
        logger.warning("push send_to_user crashed (user=%s): %s", user_id, e)
        db.rollback()
    finally:
        db.close()
