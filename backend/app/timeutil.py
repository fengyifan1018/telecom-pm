"""统一时间工具：系统存储与展示均使用东八区（naive），JWT exp 仍用 UTC。"""
from datetime import datetime, timezone, timedelta

CN_TZ = timezone(timedelta(hours=8))


def now_cn() -> datetime:
    """当前北京时间（naive datetime，用于 ORM 默认值与业务时间戳）。"""
    return datetime.now(CN_TZ).replace(tzinfo=None)
