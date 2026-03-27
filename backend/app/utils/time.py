"""
时间工具模块。
提供时间戳转换、格式化等通用时间处理函数。
"""
from datetime import datetime, timezone, timedelta


def now_utc() -> datetime:
    """获取当前UTC时间"""
    return datetime.now(timezone.utc)


def timestamp_to_datetime(ts: int) -> datetime:
    """毫秒时间戳转datetime"""
    return datetime.fromtimestamp(ts / 1000, tz=timezone.utc)


def datetime_to_timestamp(dt: datetime) -> int:
    """datetime转毫秒时间戳"""
    return int(dt.timestamp() * 1000)


def format_datetime(dt: datetime) -> str:
    """格式化datetime为字符串"""
    if dt is None:
        return ""
    return dt.strftime("%Y-%m-%d %H:%M:%S")


def parse_datetime(s: str) -> datetime:
    """解析时间字符串"""
    for fmt in ["%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d"]:
        try:
            return datetime.strptime(s, fmt).replace(tzinfo=timezone.utc)
        except ValueError:
            continue
    raise ValueError(f"无法解析时间字符串: {s}")


def time_ago(dt: datetime) -> str:
    """将时间转换为人类可读的相对时间"""
    if dt is None:
        return "未知"

    now = now_utc()
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)

    delta = now - dt
    seconds = int(delta.total_seconds())

    if seconds < 60:
        return f"{seconds}秒前"
    elif seconds < 3600:
        return f"{seconds // 60}分钟前"
    elif seconds < 86400:
        return f"{seconds // 3600}小时前"
    elif seconds < 2592000:
        return f"{seconds // 86400}天前"
    else:
        return format_datetime(dt)
