"""
异常检测引擎 —— 三级组合检测。

检测方法:
  第一级: Z-score（2σ）—— 主检测器，捕获显著偏离
  第二级: 7日滚动平均偏离 —— 趋势检测器，捕获渐进恶化
  第三级: IQR 箱线图 —— 鲁棒校验器，对偏态分布敏感

综合判定:
  ≥2 级命中 → 🔴 确认异常
  1 级命中   → 🟡 疑似异常（建议关注）
  0 级命中   → 🟢 正常

额外规则:
  - 连续 ≥3 天满意度下降 → 持续恶化预警
  - 未解决率 > 整体均值 + 15% → 解决能力预警
  - 分类占比突增（Z-score > 2σ 且占比 > 30%）

每个异常均包含: evidence（判断依据）, related_ticket_ids（涉及工单）, suggestion（建议行动）
"""

from datetime import date
from typing import Any

import pandas as pd
import numpy as np


# ==================== 检测器核心函数 ====================

def zscore_detect(series: pd.Series, threshold: float = 2.0) -> tuple[pd.Series, float, float]:
    """
    Z-score 异常检测。
    返回 (flag_series, mean, std)。
    """
    mean = series.mean()
    std = series.std()
    if std == 0:
        return pd.Series([False] * len(series), index=series.index), mean, std
    z = (series - mean).abs() / std
    return z > threshold, mean, std


def zscore_low_detect(series: pd.Series, threshold: float = 2.0) -> tuple[pd.Series, float, float]:
    """
    Z-score 单边检测（仅检测低值方向，用于满意度下降检测）。
    返回 (flag_series, mean, std)。
    """
    mean = series.mean()
    std = series.std()
    if std == 0:
        return pd.Series([False] * len(series), index=series.index), mean, std
    z = (mean - series) / std
    return z > threshold, mean, std


def rolling_deviation_detect(
    series: pd.Series,
    window: int = 7,
    deviation_pct: float = 0.30
) -> tuple[pd.Series, pd.Series]:
    """
    滚动平均偏离检测。
    返回 (flag_series, rolling_means)。
    """
    rolling = series.rolling(window=window, min_periods=max(1, window // 2)).mean()
    with np.errstate(divide="ignore", invalid="ignore"):
        pct = ((series - rolling).abs() / rolling.replace(0, np.nan))
    return pct > deviation_pct, rolling


def iqr_detect(series: pd.Series, multiplier: float = 1.5) -> tuple[pd.Series, float, float, float, float]:
    """
    IQR 箱线图异常检测。
    返回 (flag_series, q1, q3, iqr, lower, upper)。
    """
    q1 = series.quantile(0.25)
    q3 = series.quantile(0.75)
    iqr = q3 - q1
    lower = q1 - multiplier * iqr
    upper = q3 + multiplier * iqr
    return (series < lower) | (series > upper), q1, q3, iqr, lower, upper


def iqr_low_detect(series: pd.Series, multiplier: float = 1.5) -> tuple[pd.Series, float, float, float, float]:
    """
    IQR 单边检测（仅检测低值方向，用于满意度下降检测）。
    """
    q1 = series.quantile(0.25)
    q3 = series.quantile(0.75)
    iqr = q3 - q1
    lower = q1 - multiplier * iqr
    upper = q3 + multiplier * iqr  # noqa (unused but for completeness)
    return (series < lower), q1, q3, iqr, lower, upper


# ==================== 工单 ID 查询辅助 ====================

def _get_tickets_in_date_range(df: pd.DataFrame, start_d: date, end_d: date) -> pd.DataFrame:
    """获取日期范围内的工单。"""
    return df[(df["date"] >= start_d) & (df["date"] <= end_d)]


def _get_tickets_by_category(df: pd.DataFrame, category: str) -> pd.DataFrame:
    """获取指定分类的工单。"""
    return df[df["category"] == category]


def _describe_tickets(df: pd.DataFrame) -> str:
    """生成工单集合的简要描述。"""
    if len(df) == 0:
        return "无工单"
    cats = df["category"].value_counts()
    parts = [f"{c}({n}条)" for c, n in cats.items()]
    return ", ".join(parts[:4])


# ==================== 建议生成 ====================

def _suggest_for_satisfaction_decline(decline_df: pd.DataFrame) -> str:
    """为满意度下降生成行动建议。"""
    suggestions = []
    # 找出满意度最低的工单
    low_tickets = decline_df[decline_df["satisfaction"] <= 2]
    unresolved = decline_df[~decline_df["is_resolved"]]

    if len(unresolved) > 0:
        unresolved_ids = ", ".join(unresolved["ticket_id"].tolist())
        suggestions.append(f"优先处理未解决工单: {unresolved_ids}")
    if len(low_tickets) > 0:
        worst_cat = low_tickets["category"].value_counts().index[0]
        suggestions.append(f"重点关注「{worst_cat}」类工单的服务质量")
    suggestions.append("建议回顾该时段客服对话记录，排查是否存在服务态度或流程问题")
    return "；".join(suggestions)


def _suggest_for_unresolved(df: pd.DataFrame, category: str) -> str:
    """为未解决率异常生成行动建议。"""
    unresolved = df[(df["category"] == category) & (~df["is_resolved"])]
    suggestions = [
        f"立即排查「{category}」分类中 {len(unresolved)} 条未解决工单的阻塞原因",
        "建议设置「退款退货」超时自动升级规则（如超过72小时未解决自动上报主管）",
        "检查退款审批流程是否存在跨部门协作瓶颈",
    ]
    return "；".join(suggestions)


def _suggest_for_volume_spike(df: pd.DataFrame, date_val: date) -> str:
    """为工单量突增生成建议。"""
    day_data = df[df["date"] == date_val]
    top_cat = day_data["category"].value_counts().index[0]
    return f"建议查看 {date_val} 当天是否有促销活动或系统故障导致「{top_cat}」工单激增；如为周期性高峰，可提前调配人手"


# ==================== 综合检测 ====================

def detect_daily_volume_anomalies(df: pd.DataFrame, daily_df: pd.DataFrame) -> pd.DataFrame:
    """检测日工单量的异常。"""
    result = daily_df.copy()
    series = result["ticket_count"]

    z_flag, z_mean, z_std = zscore_detect(series)
    r_flag, r_means = rolling_deviation_detect(series)
    i_flag, iq1, iq3, iqr_v, ilow, ihigh = iqr_detect(series)

    result["zscore_flag"] = z_flag
    result["rolling_flag"] = r_flag
    result["iqr_flag"] = i_flag
    result["hit_count"] = result[["zscore_flag", "rolling_flag", "iqr_flag"]].sum(axis=1)
    result["anomaly_level"] = result["hit_count"].map({0: "🟢 正常", 1: "🟡 疑似", 2: "🔴 确认", 3: "🔴 确认"})
    result["anomaly_type"] = "工单量异常"

    # 为异常日生成证据
    result["evidence"] = ""
    result["related_ticket_ids"] = ""
    result["suggestion"] = ""
    for idx in result[result["hit_count"] >= 1].index:
        row = result.loc[idx]
        date_val = row["date"]
        val = row["ticket_count"]
        day_tickets = _get_tickets_in_date_range(df, date_val, date_val)

        evidence_parts = []
        if row["zscore_flag"]:
            evidence_parts.append(f"Z-score={abs(val - z_mean) / z_std:.1f}>2.0（均值{z_mean:.1f}，标准差{z_std:.1f}）")
        if row["rolling_flag"]:
            evidence_parts.append(f"滚动均值偏离={(abs(val - r_means.loc[idx]) / r_means.loc[idx] * 100):.0f}%>30%（滚动均值{r_means.loc[idx]:.1f}）")
        if row["iqr_flag"]:
            evidence_parts.append(f"超出IQR范围[{ilow:.1f}, {ihigh:.1f}]")

        result.at[idx, "evidence"] = "；".join(evidence_parts)
        result.at[idx, "related_ticket_ids"] = ", ".join(day_tickets["ticket_id"].tolist())
        result.at[idx, "suggestion"] = _suggest_for_volume_spike(df, date_val)

    return result


def detect_satisfaction_anomalies(df: pd.DataFrame, daily_df: pd.DataFrame) -> pd.DataFrame:
    """检测日满意度均值的异常（低满意度方向）。"""
    result = daily_df.copy()
    series = result["avg_satisfaction"]

    z_flag_low, z_mean, z_std = zscore_low_detect(series)
    r_flag, r_means = rolling_deviation_detect(series)
    i_flag_low, iq1, iq3, iqr_v, ilow, ihigh = iqr_low_detect(series)

    result["zscore_flag"] = z_flag_low
    result["rolling_flag"] = r_flag
    result["iqr_flag"] = i_flag_low
    result["hit_count"] = result[["zscore_flag", "rolling_flag", "iqr_flag"]].sum(axis=1)
    result["anomaly_level"] = result["hit_count"].map({0: "🟢 正常", 1: "🟡 疑似", 2: "🔴 确认", 3: "🔴 确认"})
    result["anomaly_type"] = "满意度异常"

    # 为异常日生成证据
    result["evidence"] = ""
    result["related_ticket_ids"] = ""
    result["suggestion"] = ""
    for idx in result[result["hit_count"] >= 1].index:
        row = result.loc[idx]
        date_val = row["date"]
        val = row["avg_satisfaction"]
        day_tickets = _get_tickets_in_date_range(df, date_val, date_val)

        evidence_parts = []
        if row["zscore_flag"]:
            evidence_parts.append(f"Z-score低值={(z_mean - val) / z_std:.1f}>2.0（均值{z_mean:.2f}，标准差{z_std:.2f}）")
        if row["rolling_flag"]:
            evidence_parts.append(f"低于滚动均值{(abs(val - r_means.loc[idx]) / r_means.loc[idx] * 100):.0f}%>30%（滚动均值{r_means.loc[idx]:.2f}）")
        if row["iqr_flag"]:
            evidence_parts.append(f"低于IQR下界{ilow:.2f}（Q1={iq1:.2f}）")

        low_count = (day_tickets["satisfaction"] <= 2).sum()
        evidence_parts.append(f"当日{len(day_tickets)}条工单中{low_count}条满意度≤2分")

        result.at[idx, "evidence"] = "；".join(evidence_parts)
        result.at[idx, "related_ticket_ids"] = ", ".join(day_tickets["ticket_id"].tolist())
        result.at[idx, "suggestion"] = _suggest_for_satisfaction_decline(day_tickets)

    return result


def detect_consecutive_satisfaction_decline(df: pd.DataFrame, daily_df: pd.DataFrame, min_days: int = 3) -> list[dict]:
    """检测满意度连续下降。"""
    values = daily_df["avg_satisfaction"].values
    dates = daily_df["date"].values
    declines = []

    def _build_decline(start: int, end: int) -> dict:
        start_d = pd.Timestamp(dates[start]).date()
        end_d = pd.Timestamp(dates[end]).date()
        period_tickets = _get_tickets_in_date_range(df, start_d, end_d)
        low_tickets = period_tickets[period_tickets["satisfaction"] <= 2]
        worst_cats = period_tickets["category"].value_counts()

        # 证据
        evidence = [
            f"连续 {end - start + 1} 天满意度下降 ({dates[start]} → {dates[end]})",
            f"期间共 {len(period_tickets)} 条工单，{len(low_tickets)} 条低分(≤2)",
            f"满意度从 {values[start]:.2f} 降至 {values[end]:.2f}，降幅 {values[start] - values[end]:.2f}",
        ]
        if len(worst_cats) > 0:
            evidence.append(f"高频分类: {worst_cats.index[0]}({worst_cats.iloc[0]}条)")

        # 涉及工单
        ticket_ids = ", ".join(period_tickets["ticket_id"].tolist())

        return {
            "type": "满意度连续下降",
            "level": "🔴 确认",
            "start_date": str(dates[start]),
            "end_date": str(dates[end]),
            "days": end - start + 1,
            "from_value": round(values[start], 2),
            "to_value": round(values[end], 2),
            "description": f"连续 {end - start + 1} 天满意度下降: {values[start]:.2f} → {values[end]:.2f}",
            "evidence": "；".join(evidence),
            "related_ticket_ids": ticket_ids,
            "suggestion": _suggest_for_satisfaction_decline(period_tickets),
        }

    current_streak_start = 0
    for i in range(1, len(values)):
        if values[i] < values[i - 1]:
            continue
        else:
            if i - current_streak_start >= min_days:
                declines.append(_build_decline(current_streak_start, i - 1))
            current_streak_start = i

    # 末尾
    if len(values) - current_streak_start >= min_days:
        declines.append(_build_decline(current_streak_start, len(values) - 1))

    return declines


def detect_category_spike(df: pd.DataFrame, daily_cat_df: pd.DataFrame) -> list[dict]:
    """检测分类占比突增（某分类在整体中的占比异常升高）。"""
    anomalies = []
    total_daily = daily_cat_df.sum(axis=1)
    proportions = daily_cat_df.div(total_daily, axis=0)

    for cat in proportions.columns:
        series = proportions[cat]
        mean_pct = series.mean()
        std_pct = series.std()
        if std_pct == 0:
            continue
        for i in range(len(series)):
            z = (series.iloc[i] - mean_pct) / std_pct
            if z > 2.0 and series.iloc[i] > 0.3:
                date_val = series.index[i]
                day_tickets = _get_tickets_in_date_range(df, date_val, date_val)
                cat_tickets = _get_tickets_by_category(day_tickets, cat)

                anomalies.append({
                    "type": "分类占比突增",
                    "level": "🔴 确认",
                    "date": str(date_val),
                    "category": cat,
                    "proportion": round(series.iloc[i] * 100, 1),
                    "mean_proportion": round(mean_pct * 100, 1),
                    "description": f"{cat} 在 {date_val} 占比突增至 {series.iloc[i]*100:.1f}%（均值 {mean_pct*100:.1f}%）",
                    "evidence": f"Z-score={z:.1f}>2.0；占比{series.iloc[i]*100:.1f}%远超均值{mean_pct*100:.1f}%（标准差{std_pct*100:.1f}%）",
                    "related_ticket_ids": ", ".join(cat_tickets["ticket_id"].tolist()),
                    "suggestion": f"建议排查 {date_val} 当天「{cat}」类工单突增原因，确认是否为系统故障、政策变更或外部事件导致",
                })

    return anomalies


def detect_unresolved_rate_alert(df: pd.DataFrame) -> list[dict]:
    """检测未解决率异常。"""
    overall_rate = (~df["is_resolved"]).mean()
    threshold = overall_rate + 0.15
    alerts = []

    for cat in df["category"].unique():
        cat_df = df[df["category"] == cat]
        cat_rate = (~cat_df["is_resolved"]).mean()
        if cat_rate > threshold:
            unresolved_df = cat_df[~cat_df["is_resolved"]]
            level = "🟡 疑似" if cat_rate < threshold + 0.1 else "🔴 确认"

            alerts.append({
                "type": "未解决率异常",
                "level": level,
                "category": cat,
                "unresolved_rate": round(cat_rate * 100, 1),
                "overall_rate": round(overall_rate * 100, 1),
                "description": f"{cat} 未解决率 {cat_rate*100:.1f}%，远超整体 {overall_rate*100:.1f}%",
                "evidence": f"「{cat}」未解决率{cat_rate*100:.1f}% > 整体{overall_rate*100:.1f}% + 15% = {threshold*100:.1f}%；{len(cat_df)}条工单中{len(unresolved_df)}条未解决",
                "related_ticket_ids": ", ".join(unresolved_df["ticket_id"].tolist()),
                "suggestion": _suggest_for_unresolved(df, cat),
                })

    return alerts


# ==================== 综合报告生成 ====================

def generate_anomaly_report(
    df: pd.DataFrame,
    daily_df: pd.DataFrame,
    daily_cat_df: pd.DataFrame,
) -> dict[str, Any]:
    """
    运行全部检测并生成综合异常报告。

    返回:
        {
            "volume_detail": DataFrame,
            "satisfaction_detail": DataFrame,
            "category_spikes": list[dict],
            "unresolved_alerts": list[dict],
            "decline_alerts": list[dict],
            "all_anomalies": list[dict],  # 按严重度排序
            "summary": str,
            "confirmed_count": int,
            "suspected_count": int,
        }
    """
    # 三级检测（传入原始 df 用于生成详情）
    vol_anomalies = detect_daily_volume_anomalies(df, daily_df)
    sat_anomalies = detect_satisfaction_anomalies(df, daily_df)

    # 额外规则
    cat_spikes = detect_category_spike(df, daily_cat_df)
    unresolved_alerts = detect_unresolved_rate_alert(df)
    decline_alerts = detect_consecutive_satisfaction_decline(df, daily_df)

    # 汇总日级异常（只保留非正常的）
    vol_issues = vol_anomalies[vol_anomalies["hit_count"] >= 1][
        ["date", "ticket_count", "anomaly_level", "anomaly_type",
         "evidence", "related_ticket_ids", "suggestion"]
    ].to_dict("records")

    sat_issues = sat_anomalies[sat_anomalies["hit_count"] >= 1][
        ["date", "avg_satisfaction", "anomaly_level", "anomaly_type",
         "evidence", "related_ticket_ids", "suggestion"]
    ].to_dict("records")

    # 统一所有异常的 schema
    all_anomalies = []
    for item in vol_issues:
        all_anomalies.append({
            "type": item["anomaly_type"],
            "level": item["anomaly_level"],
            "date": str(item["date"]),
            "description": f"{item['date']} 工单量 {item['ticket_count']} 条，{item['anomaly_level']}",
            "evidence": item.get("evidence", ""),
            "related_ticket_ids": item.get("related_ticket_ids", ""),
            "suggestion": item.get("suggestion", ""),
        })

    for item in sat_issues:
        all_anomalies.append({
            "type": item["anomaly_type"],
            "level": item["anomaly_level"],
            "date": str(item["date"]),
            "description": f"{item['date']} 满意度均值 {item['avg_satisfaction']:.2f}，{item['anomaly_level']}",
            "evidence": item.get("evidence", ""),
            "related_ticket_ids": item.get("related_ticket_ids", ""),
            "suggestion": item.get("suggestion", ""),
        })

    for item in cat_spikes:
        all_anomalies.append(item)

    for item in unresolved_alerts:
        all_anomalies.append(item)

    for item in decline_alerts:
        all_anomalies.append(item)

    # 按严重度排序：确认 > 疑似
    all_anomalies.sort(key=lambda x: (0 if "确认" in x.get("level", "") else 1, x.get("date", x.get("start_date", ""))))

    # 总结
    confirmed = [a for a in all_anomalies if "确认" in a.get("level", "")]
    suspected = [a for a in all_anomalies if "疑似" in a.get("level", "")]

    summary_parts = []
    if confirmed:
        summary_parts.append(f"发现 {len(confirmed)} 个确认异常信号")
    if suspected:
        summary_parts.append(f"发现 {len(suspected)} 个疑似异常信号")
    if not summary_parts:
        summary_parts.append("未发现明显异常信号，系统运行正常")

    # 保留详细 DataFrame（含证据列）
    detail_cols = ["date", "ticket_count", "avg_satisfaction",
                   "zscore_flag", "rolling_flag", "iqr_flag", "hit_count",
                   "anomaly_level", "anomaly_type", "evidence",
                   "related_ticket_ids", "suggestion"]

    vol_detail = vol_anomalies[[c for c in detail_cols if c in vol_anomalies.columns]].copy()
    sat_detail = sat_anomalies[[c for c in detail_cols if c in sat_anomalies.columns]].copy()

    return {
        "volume_detail": vol_detail,
        "satisfaction_detail": sat_detail,
        "category_spikes": cat_spikes,
        "unresolved_alerts": unresolved_alerts,
        "decline_alerts": decline_alerts,
        "all_anomalies": all_anomalies,
        "summary": "\n".join(summary_parts),
        "confirmed_count": len(confirmed),
        "suspected_count": len(suspected),
    }
