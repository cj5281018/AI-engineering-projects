"""
数据加载与预处理模块。
负责加载 JSON 工单数据，解析日期，生成衍生字段，并提供筛选接口。
"""

import json
from pathlib import Path
from datetime import date
from typing import Optional

import pandas as pd


# 数据文件路径
DATA_DIR = Path(__file__).parent / "3_task_requirements"
TICKETS_PATH = DATA_DIR / "task5_tickets.json"


def load_data() -> pd.DataFrame:
    """加载并预处理工单数据。"""
    with open(TICKETS_PATH, "r", encoding="utf-8") as f:
        tickets = json.load(f)

    df = pd.DataFrame(tickets)

    # 日期解析
    df["created_at"] = pd.to_datetime(df["created_at"])
    df["date"] = df["created_at"].dt.date

    # 优先级编码（用于相关性分析）
    priority_order = {"低": 1, "中": 2, "高": 3}
    df["priority_level"] = df["priority"].map(priority_order)

    # 衍生布尔标记
    df["is_high_priority"] = df["priority"] == "高"
    df["is_low_satisfaction"] = df["satisfaction"] <= 2

    return df


def filter_data(
    df: pd.DataFrame,
    date_range: Optional[tuple[date, date]] = None,
    categories: Optional[list[str]] = None,
    priorities: Optional[list[str]] = None,
    channels: Optional[list[str]] = None,
) -> pd.DataFrame:
    """
    按条件筛选工单数据。
    """
    result = df.copy()

    if date_range is not None:
        start, end = date_range
        result = result[(result["date"] >= start) & (result["date"] <= end)]

    if categories:
        result = result[result["category"].isin(categories)]

    if priorities:
        result = result[result["priority"].isin(priorities)]

    if channels:
        result = result[result["channel"].isin(channels)]

    return result


def get_metadata(df: pd.DataFrame) -> dict:
    """获取数据集的基本元信息。"""
    return {
        "total_tickets": len(df),
        "date_start": df["date"].min(),
        "date_end": df["date"].max(),
        "date_range_days": (df["date"].max() - df["date"].min()).days + 1,
        "categories": sorted(df["category"].unique().tolist()),
        "priorities": sorted(df["priority"].unique().tolist(), key=lambda x: {"高": 0, "中": 1, "低": 2}.get(x, 9)),
        "channels": sorted(df["channel"].unique().tolist()),
    }
