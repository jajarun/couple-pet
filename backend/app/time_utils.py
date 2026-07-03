from datetime import datetime, timezone


def utcnow() -> datetime:
    """Naive UTC now — avoids datetime.utcnow() deprecation and aware/naive mixing."""
    return datetime.now(timezone.utc).replace(tzinfo=None)
