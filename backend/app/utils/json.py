"""
JSON工具模块。
提供支持特殊类型序列化的JSON处理函数。
"""
import json
from datetime import datetime, date
from decimal import Decimal
from typing import Any, Optional
import numpy as np


class CustomEncoder(json.JSONEncoder):
    """自定义JSON编码器，支持datetime、Decimal、numpy等类型"""

    def default(self, obj):
        if isinstance(obj, (datetime, date)):
            return obj.isoformat()
        if isinstance(obj, Decimal):
            return float(obj)
        if isinstance(obj, np.integer):
            return int(obj)
        if isinstance(obj, np.floating):
            return float(obj)
        if isinstance(obj, np.ndarray):
            return obj.tolist()
        if isinstance(obj, np.bool_):
            return bool(obj)
        return super().default(obj)


def to_json(obj: Any) -> str:
    """将对象序列化为JSON字符串"""
    return json.dumps(obj, cls=CustomEncoder, ensure_ascii=False)


def from_json(s: str) -> Any:
    """将JSON字符串反序列化为对象"""
    return json.loads(s)


def safe_get(d: dict, key: str, default: Any = None) -> Any:
    """安全获取字典值"""
    if not isinstance(d, dict):
        return default
    return d.get(key, default)
