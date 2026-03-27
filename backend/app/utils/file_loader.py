"""
文件加载工具模块。
"""
import json
from pathlib import Path
from typing import Any, Dict
import pandas as pd
from loguru import logger


def load_json_file(path: str) -> Dict[str, Any]:
    """加载JSON文件"""
    file_path = Path(path)
    if not file_path.exists():
        raise FileNotFoundError(f"文件不存在: {path}")

    with open(file_path, "r", encoding="utf-8") as f:
        return json.load(f)


def load_csv_to_dataframe(path: str) -> pd.DataFrame:
    """加载CSV文件为DataFrame"""
    file_path = Path(path)
    if not file_path.exists():
        raise FileNotFoundError(f"文件不存在: {path}")

    df = pd.read_csv(file_path)
    logger.info(f"CSV文件加载完成: {path}, 共{len(df)}行")
    return df
