"""
核心分析逻辑模块。
提供各维度的统计计算：时间趋势、分类分布、处理效率、满意度、渠道分析。
"""

import pandas as pd


# ==================== 总览 KPI ====================

def compute_kpi(df: pd.DataFrame) -> dict:
    """计算顶部 KPI 指标。"""
    total = len(df)
    return {
        "total_tickets": total,
        "avg_satisfaction": round(df["satisfaction"].mean(), 2),
        "avg_resolution_hours": round(df["resolution_time_hours"].mean(), 1),
        "unresolved_rate": round((~df["is_resolved"]).mean() * 100, 1),
        "high_priority_rate": round(df["is_high_priority"].mean() * 100, 1),
    }


# ==================== 时间趋势 ====================

def daily_trend(df: pd.DataFrame) -> pd.DataFrame:
    """每日工单量统计（含滚动均值）。"""
    all_dates = pd.date_range(df["date"].min(), df["date"].max(), freq="D")
    daily = df.groupby("date").agg(
        ticket_count=("ticket_id", "count"),
        high_priority_count=("is_high_priority", "sum"),
        avg_satisfaction=("satisfaction", "mean"),
        unresolved_count=("is_resolved", lambda x: (~x).sum()),
    ).reindex(all_dates, fill_value=0).reset_index()
    daily.columns = ["date", "ticket_count", "high_priority_count", "avg_satisfaction", "unresolved_count"]
    daily["date"] = daily["date"].dt.date
    daily["rolling_avg_7d"] = daily["ticket_count"].rolling(window=7, min_periods=1).mean()
    daily["satisfaction_rolling_3d"] = daily["avg_satisfaction"].rolling(window=3, min_periods=1).mean()
    return daily


def daily_category_trend(df: pd.DataFrame) -> pd.DataFrame:
    """每日 × 分类的工单量透视表。"""
    daily_cat = df.groupby(["date", "category"]).size().unstack(fill_value=0)
    all_dates = pd.date_range(df["date"].min(), df["date"].max(), freq="D").date
    return daily_cat.reindex(all_dates, fill_value=0)


# ==================== 分类分析 ====================

def category_stats(df: pd.DataFrame) -> pd.DataFrame:
    """各分类的综合统计。"""
    stats = df.groupby("category").agg(
        ticket_count=("ticket_id", "count"),
        avg_satisfaction=("satisfaction", "mean"),
        avg_resolution_hours=("resolution_time_hours", "mean"),
        high_priority_count=("is_high_priority", "sum"),
        unresolved_count=("is_resolved", lambda x: (~x).sum()),
    ).reset_index()
    stats["pct"] = (stats["ticket_count"] / stats["ticket_count"].sum() * 100).round(1)
    stats["high_priority_rate"] = (stats["high_priority_count"] / stats["ticket_count"] * 100).round(1)
    stats["unresolved_rate"] = (stats["unresolved_count"] / stats["ticket_count"] * 100).round(1)
    stats["avg_satisfaction"] = stats["avg_satisfaction"].round(2)
    stats["avg_resolution_hours"] = stats["avg_resolution_hours"].round(1)
    return stats.sort_values("ticket_count", ascending=False)


def category_priority_cross(df: pd.DataFrame) -> pd.DataFrame:
    """分类 × 优先级交叉表。"""
    cross = pd.crosstab(df["category"], df["priority"])
    for p in ["高", "中", "低"]:
        if p not in cross.columns:
            cross[p] = 0
    return cross[["高", "中", "低"]]


# ==================== 处理效率 ====================

def resolution_time_stats(df: pd.DataFrame) -> pd.DataFrame:
    """各分类处理时长统计。"""
    stats = df.groupby("category").agg(
        avg_hours=("resolution_time_hours", "mean"),
        median_hours=("resolution_time_hours", "median"),
        max_hours=("resolution_time_hours", "max"),
        min_hours=("resolution_time_hours", "min"),
        ticket_count=("ticket_id", "count"),
    ).reset_index()
    stats["avg_hours"] = stats["avg_hours"].round(1)
    stats["median_hours"] = stats["median_hours"].round(1)
    return stats.sort_values("avg_hours", ascending=False)


# ==================== 满意度分析 ====================

def satisfaction_stats(df: pd.DataFrame) -> dict:
    """满意度综合统计。"""
    return {
        "mean": round(df["satisfaction"].mean(), 2),
        "median": df["satisfaction"].median(),
        "std": round(df["satisfaction"].std(), 2),
        "distribution": df["satisfaction"].value_counts().sort_index().to_dict(),
        "low_rate": round((df["satisfaction"] <= 2).mean() * 100, 1),
        "high_rate": round((df["satisfaction"] >= 4).mean() * 100, 1),
    }


def satisfaction_by_channel(df: pd.DataFrame) -> pd.DataFrame:
    """各渠道满意度对比。"""
    return df.groupby("channel").agg(
        avg_satisfaction=("satisfaction", "mean"),
        median_satisfaction=("satisfaction", "median"),
        ticket_count=("ticket_id", "count"),
        low_satisfaction_rate=("is_low_satisfaction", "mean"),
    ).round(2).reset_index()


# ==================== 渠道分析 ====================

def channel_stats(df: pd.DataFrame) -> pd.DataFrame:
    """渠道综合统计。"""
    stats = df.groupby("channel").agg(
        ticket_count=("ticket_id", "count"),
        avg_satisfaction=("satisfaction", "mean"),
        avg_resolution_hours=("resolution_time_hours", "mean"),
        unresolved_rate=("is_resolved", lambda x: (~x).mean()),
    ).reset_index()
    stats["pct"] = (stats["ticket_count"] / stats["ticket_count"].sum() * 100).round(1)
    stats["avg_satisfaction"] = stats["avg_satisfaction"].round(2)
    stats["avg_resolution_hours"] = stats["avg_resolution_hours"].round(1)
    stats["unresolved_rate"] = (stats["unresolved_rate"] * 100).round(1)
    return stats.sort_values("ticket_count", ascending=False)


def channel_category_cross(df: pd.DataFrame) -> pd.DataFrame:
    """渠道 × 分类交叉表。"""
    return pd.crosstab(df["channel"], df["category"])


# ==================== 关联分析 ====================

def resolution_vs_satisfaction(df: pd.DataFrame) -> pd.DataFrame:
    """处理时长分段 × 满意度。"""
    df = df.copy()
    bins = [0, 2, 8, 24, 48, 200]
    labels = ["<2h", "2-8h", "8-24h", "24-48h", ">48h"]
    df["time_bucket"] = pd.cut(df["resolution_time_hours"], bins=bins, labels=labels)
    return df.groupby("time_bucket", observed=False).agg(
        avg_satisfaction=("satisfaction", "mean"),
        ticket_count=("ticket_id", "count"),
    ).round(2).reset_index()
