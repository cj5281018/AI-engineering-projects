"""
图表生成模块。
基于 Matplotlib + Seaborn，适配中文字体，生成所有可视化图表。
每个函数返回 matplotlib.figure.Figure 对象。
"""

import platform
from io import BytesIO

import pandas as pd
import matplotlib
import matplotlib.pyplot as plt
import seaborn as sns

from utils import (
    PALETTE_6, PRIORITY_COLORS,
    COLOR_DANGER, COLOR_WARNING, COLOR_SUCCESS, COLOR_INFO,
    set_style, fig_to_png_bytes,
)

# ==================== 中文字体配置 ====================

def _setup_chinese_font():
    """配置 Matplotlib 中文字体。"""
    import matplotlib.font_manager as fm

    system = platform.system()
    if system == "Windows":
        font_candidates = [
            "Microsoft YaHei", "SimHei", "KaiTi", "FangSong", "SimSun",
        ]
    elif system == "Darwin":
        font_candidates = [
            "PingFang SC", "Heiti SC", "STHeiti", "Arial Unicode MS",
        ]
    else:
        font_candidates = [
            "WenQuanYi Micro Hei", "WenQuanYi Zen Hei", "Noto Sans CJK SC",
            "Droid Sans Fallback", "DejaVu Sans",
        ]

    try:
        fm._load_fontmanager(try_read_cache=False)
    except Exception:
        pass

    available_fonts = {f.name for f in fm.fontManager.ttflist}

    selected = None
    for font in font_candidates:
        if font in available_fonts:
            selected = font
            break

    if selected:
        plt.rcParams["font.family"] = selected
        plt.rcParams["font.sans-serif"] = [selected] + plt.rcParams.get("font.sans-serif", ["DejaVu Sans"])
    else:
        plt.rcParams["font.family"] = "sans-serif"
        plt.rcParams["font.sans-serif"] = ["SimHei"] + plt.rcParams.get("font.sans-serif", ["DejaVu Sans"])

    plt.rcParams["axes.unicode_minus"] = False


_setup_chinese_font()
set_style()
_setup_chinese_font()  # set_style 会重置 font.family，重新设置

CATEGORY_COLORS = {}


def _get_category_colors(categories: list[str]) -> dict[str, str]:
    """为分类列表分配颜色。"""
    global CATEGORY_COLORS
    if not CATEGORY_COLORS:
        palette = sns.color_palette(PALETTE_6, n_colors=max(len(categories), 6))
        for i, cat in enumerate(categories):
            CATEGORY_COLORS[cat] = palette[i % len(palette)]
    return CATEGORY_COLORS


# ==================== 图表尺寸常量 ====================

FIG_SIZE_WIDE = (10, 4.5)
FIG_SIZE_SQUARE = (6, 5)
FIG_SIZE_HALF = (5.5, 4)
FIG_SIZE_HEATMAP = (7, 5)


# ==================== 总览模块 ====================

def plot_category_donut(cat_stats: pd.DataFrame) -> plt.Figure:
    """分类占比环形图。"""
    fig, ax = plt.subplots(figsize=FIG_SIZE_SQUARE)
    colors = _get_category_colors(cat_stats["category"].tolist())

    wedges, texts, autotexts = ax.pie(
        cat_stats["ticket_count"],
        labels=cat_stats["category"],
        autopct="%1.1f%%",
        startangle=140,
        pctdistance=0.78,
        colors=[colors.get(c, PALETTE_6[i % 6]) for i, c in enumerate(cat_stats["category"])],
        wedgeprops={"width": 0.4, "edgecolor": "white", "linewidth": 1.5},
    )
    for t in autotexts:
        t.set_fontsize(8)
    for t in texts:
        t.set_fontsize(10)
    ax.set_title("工单分类占比", fontsize=14, fontweight="bold", pad=15)
    return fig


def plot_priority_pie(df: pd.DataFrame) -> plt.Figure:
    """优先级分布环形图。"""
    priority_counts = df["priority"].value_counts()
    order = ["高", "中", "低"]
    sizes = [priority_counts.get(p, 0) for p in order]
    colors = [PRIORITY_COLORS[p] for p in order]

    fig, ax = plt.subplots(figsize=(5, 4.5))
    wedges, texts, autotexts = ax.pie(
        sizes, labels=order, autopct="%1.1f%%", startangle=90,
        pctdistance=0.78, colors=colors,
        wedgeprops={"width": 0.4, "edgecolor": "white", "linewidth": 1.5},
    )
    for t in autotexts:
        t.set_fontsize(9)
    for t in texts:
        t.set_fontsize(11)
    ax.set_title("优先级分布", fontsize=14, fontweight="bold", pad=15)
    return fig


# ==================== 时间趋势模块 ====================

def plot_daily_volume_trend(daily_df: pd.DataFrame) -> plt.Figure:
    """每日工单量折线图 + 7日滚动平均 + 高优先级标注。"""
    fig, ax1 = plt.subplots(figsize=FIG_SIZE_WIDE)
    dates = daily_df["date"].astype(str)

    ax1.plot(dates, daily_df["ticket_count"],
             marker="o", color=COLOR_INFO, linewidth=2, markersize=6,
             label="每日工单量", zorder=3)
    ax1.plot(dates, daily_df["rolling_avg_7d"],
             color=COLOR_WARNING, linewidth=2, linestyle="--",
             label="7日滚动均值", zorder=2)
    ax1.fill_between(range(len(dates)), daily_df["ticket_count"],
                     alpha=0.15, color=COLOR_INFO)
    ax1.set_xlabel("日期", fontsize=11)
    ax1.set_ylabel("工单数量", fontsize=11, color=COLOR_INFO)
    ax1.tick_params(axis="y", labelcolor=COLOR_INFO)

    ax2 = ax1.twinx()
    ax2.bar(dates, daily_df["high_priority_count"],
            alpha=0.3, color=COLOR_DANGER, label="高优先级工单")
    ax2.set_ylabel("高优先级数量", fontsize=11, color=COLOR_DANGER)
    ax2.tick_params(axis="y", labelcolor=COLOR_DANGER)

    lines1, labels1 = ax1.get_legend_handles_labels()
    lines2, labels2 = ax2.get_legend_handles_labels()
    ax1.legend(lines1 + lines2, labels1 + labels2, loc="upper left", frameon=True)
    fig.autofmt_xdate(rotation=45, ha="right")
    ax1.set_title("每日工单量趋势", fontsize=14, fontweight="bold", pad=15)
    ax1.grid(True, alpha=0.3)
    return fig


def plot_category_stacked_area(daily_cat_df: pd.DataFrame) -> plt.Figure:
    """各分类逐日堆叠面积图。"""
    fig, ax = plt.subplots(figsize=FIG_SIZE_WIDE)
    dates = [str(d) for d in daily_cat_df.index]
    categories = daily_cat_df.columns.tolist()
    colors = _get_category_colors(categories)

    ax.stackplot(
        range(len(dates)),
        *[daily_cat_df[cat].values for cat in categories],
        labels=categories,
        colors=[colors.get(c, PALETTE_6[i % 6]) for i, c in enumerate(categories)],
        alpha=0.8,
    )
    ax.set_xticks(range(len(dates)))
    ax.set_xticklabels(dates, rotation=45, ha="right")
    ax.set_ylabel("工单数量", fontsize=11)
    ax.set_title("各分类逐日工单量（堆叠面积）", fontsize=14, fontweight="bold", pad=15)
    ax.legend(loc="upper left", frameon=True, ncol=2, fontsize=8)
    ax.grid(True, alpha=0.3)
    return fig


def plot_priority_daily_trend(daily_df: pd.DataFrame, df: pd.DataFrame) -> plt.Figure:
    """高/中/低优先级日趋势（分面图）。"""
    daily_priority = df.groupby(["date", "priority"]).size().unstack(fill_value=0)
    for p in ["高", "中", "低"]:
        if p not in daily_priority.columns:
            daily_priority[p] = 0
    daily_priority = daily_priority[["高", "中", "低"]]

    fig, axes = plt.subplots(3, 1, figsize=(10, 7), sharex=True)
    for idx, priority in enumerate(["高", "中", "低"]):
        ax = axes[idx]
        ax.fill_between(range(len(daily_priority)), daily_priority[priority].values,
                        alpha=0.3, color=PRIORITY_COLORS[priority])
        ax.plot(range(len(daily_priority)), daily_priority[priority].values,
                marker="o", color=PRIORITY_COLORS[priority], linewidth=1.8, markersize=5)
        ax.set_ylabel(priority, fontsize=11, color=PRIORITY_COLORS[priority])
        ax.grid(True, alpha=0.3)
        ax.set_ylim(bottom=0)

    dates = [str(d) for d in daily_priority.index]
    axes[-1].set_xticks(range(len(dates)))
    axes[-1].set_xticklabels(dates, rotation=45, ha="right")
    fig.suptitle("各优先级日工单量趋势", fontsize=14, fontweight="bold", y=1.01)
    fig.tight_layout()
    return fig


# ==================== 分类分析模块 ====================

def plot_category_bar(cat_stats: pd.DataFrame) -> plt.Figure:
    """分类工单量横向柱状图（降序）。"""
    fig, ax = plt.subplots(figsize=FIG_SIZE_HALF)
    colors = _get_category_colors(cat_stats["category"].tolist())

    bars = ax.barh(
        cat_stats["category"], cat_stats["ticket_count"],
        color=[colors.get(c, PALETTE_6[i % 6]) for i, c in enumerate(cat_stats["category"])],
        edgecolor="white", linewidth=0.8, height=0.6,
    )
    for bar, val, pct in zip(bars, cat_stats["ticket_count"], cat_stats["pct"]):
        ax.text(bar.get_width() + 0.2, bar.get_y() + bar.get_height() / 2,
                f"{val} ({pct}%)", va="center", fontsize=9)
    ax.set_xlabel("工单数量", fontsize=11)
    ax.set_title("各分类工单量排行", fontsize=14, fontweight="bold", pad=15)
    ax.invert_yaxis()
    ax.grid(True, alpha=0.3, axis="x")
    return fig


def plot_category_priority_heatmap(cross_df: pd.DataFrame) -> plt.Figure:
    """分类 × 优先级热力图。"""
    fig, ax = plt.subplots(figsize=FIG_SIZE_HEATMAP)
    sns.heatmap(cross_df, annot=True, fmt="d", cmap="YlOrRd",
                linewidths=1.5, linecolor="white",
                cbar_kws={"label": "工单数量"}, ax=ax, square=True)
    ax.set_title("分类 × 优先级 交叉热力图", fontsize=14, fontweight="bold", pad=15)
    ax.set_xlabel("优先级", fontsize=11)
    ax.set_ylabel("分类", fontsize=11)
    return fig


def plot_category_satisfaction(cat_stats: pd.DataFrame) -> plt.Figure:
    """各分类满意度均值对比柱状图。"""
    fig, ax = plt.subplots(figsize=FIG_SIZE_HALF)
    colors = _get_category_colors(cat_stats["category"].tolist())
    overall_mean = cat_stats["avg_satisfaction"].mean()

    bars = ax.bar(
        range(len(cat_stats)), cat_stats["avg_satisfaction"],
        color=[colors.get(c, PALETTE_6[i % 6]) for i, c in enumerate(cat_stats["category"])],
        edgecolor="white", linewidth=0.8,
    )
    ax.axhline(overall_mean, color=COLOR_DANGER, linestyle="--", linewidth=1.5,
               label=f"整体均值: {overall_mean:.2f}", alpha=0.7)
    for bar, val in zip(bars, cat_stats["avg_satisfaction"]):
        ax.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + 0.03,
                f"{val:.2f}", ha="center", fontsize=9)
    ax.set_xticks(range(len(cat_stats)))
    ax.set_xticklabels(cat_stats["category"], rotation=30, ha="right")
    ax.set_ylabel("平均满意度", fontsize=11)
    ax.set_title("各分类满意度对比", fontsize=14, fontweight="bold", pad=15)
    ax.legend(fontsize=9)
    ax.set_ylim(0, 5.5)
    ax.grid(True, alpha=0.3, axis="y")
    return fig


# ==================== 处理效率模块 ====================

def plot_resolution_time_bar(res_time_df: pd.DataFrame) -> plt.Figure:
    """各分类平均处理时长横向柱状图。"""
    fig, ax = plt.subplots(figsize=FIG_SIZE_HALF)
    colors = _get_category_colors(res_time_df["category"].tolist())

    bars = ax.barh(
        res_time_df["category"], res_time_df["avg_hours"],
        color=[colors.get(c, PALETTE_6[i % 6]) for i, c in enumerate(res_time_df["category"])],
        edgecolor="white", linewidth=0.8, height=0.6,
    )
    for bar, val in zip(bars, res_time_df["avg_hours"]):
        ax.text(bar.get_width() + 0.3, bar.get_y() + bar.get_height() / 2,
                f"{val:.1f}h", va="center", fontsize=9)
    ax.set_xlabel("平均处理时长（小时）", fontsize=11)
    ax.set_title("各分类平均处理时长", fontsize=14, fontweight="bold", pad=15)
    ax.invert_yaxis()
    ax.grid(True, alpha=0.3, axis="x")
    return fig


def plot_priority_boxplot(df: pd.DataFrame) -> plt.Figure:
    """各优先级处理时长箱线图。"""
    fig, ax = plt.subplots(figsize=FIG_SIZE_HALF)
    order = ["高", "中", "低"]
    bp = ax.boxplot(
        [df[df["priority"] == p]["resolution_time_hours"].values for p in order],
        labels=order, patch_artist=True, widths=0.5,
    )
    for patch, color in zip(bp["boxes"], [PRIORITY_COLORS[p] for p in order]):
        patch.set_facecolor(color)
        patch.set_alpha(0.5)
    ax.set_ylabel("处理时长（小时）", fontsize=11)
    ax.set_title("各优先级处理时长分布", fontsize=14, fontweight="bold", pad=15)
    ax.grid(True, alpha=0.3, axis="y")
    return fig


def plot_resolution_vs_satisfaction(df: pd.DataFrame) -> plt.Figure:
    """处理时长 vs 满意度散点图 + 回归线。"""
    fig, ax = plt.subplots(figsize=FIG_SIZE_SQUARE)
    categories = df["category"].unique()
    colors = _get_category_colors(categories)

    for cat in categories:
        cat_data = df[df["category"] == cat]
        ax.scatter(cat_data["resolution_time_hours"], cat_data["satisfaction"],
                   label=cat, color=colors.get(cat, "gray"),
                   alpha=0.7, s=60, edgecolors="white", linewidth=0.5)
    sns.regplot(data=df, x="resolution_time_hours", y="satisfaction",
                scatter=False, ax=ax, color=COLOR_DANGER,
                line_kws={"linewidth": 2, "linestyle": "--", "alpha": 0.6})
    ax.set_xlabel("处理时长（小时）", fontsize=11)
    ax.set_ylabel("满意度评分", fontsize=11)
    ax.set_title("处理时长 vs 满意度", fontsize=14, fontweight="bold", pad=15)
    ax.legend(fontsize=8, ncol=2)
    ax.grid(True, alpha=0.3)
    return fig


# ==================== 满意度分析模块 ====================

def plot_satisfaction_distribution(df: pd.DataFrame) -> plt.Figure:
    """满意度分布直方图 + KDE。"""
    fig, ax = plt.subplots(figsize=FIG_SIZE_HALF)
    sns.histplot(df["satisfaction"], bins=5, discrete=True, kde=True,
                 color=COLOR_INFO, alpha=0.5, edgecolor="white", linewidth=1, ax=ax)
    mean_val = df["satisfaction"].mean()
    ax.axvline(mean_val, color=COLOR_DANGER, linestyle="--", linewidth=2,
               label=f"均值: {mean_val:.2f}")
    ax.set_xlabel("满意度评分", fontsize=11)
    ax.set_ylabel("工单数量", fontsize=11)
    ax.set_title("满意度分布", fontsize=14, fontweight="bold", pad=15)
    ax.legend(fontsize=10)
    ax.grid(True, alpha=0.3)
    return fig


def plot_satisfaction_by_channel(sat_df: pd.DataFrame) -> plt.Figure:
    """各渠道满意度分组柱状图。"""
    fig, ax = plt.subplots(figsize=FIG_SIZE_HALF)
    x = range(len(sat_df))
    width = 0.35

    ax.bar([i - width / 2 for i in x], sat_df["avg_satisfaction"],
           width, color=COLOR_INFO, alpha=0.8, label="平均满意度")
    ax2 = ax.twinx()
    ax2.bar([i + width / 2 for i in x], sat_df["low_satisfaction_rate"] * 100,
            width, color=COLOR_DANGER, alpha=0.5, label="低满意度率(%)")

    ax.set_xticks(x)
    ax.set_xticklabels(sat_df["channel"])
    ax.set_ylabel("平均满意度", fontsize=11, color=COLOR_INFO)
    ax2.set_ylabel("低满意度率 (%)", fontsize=11, color=COLOR_DANGER)
    ax.set_ylim(0, 5.5)
    lines1, labels1 = ax.get_legend_handles_labels()
    lines2, labels2 = ax2.get_legend_handles_labels()
    ax.legend(lines1 + lines2, labels1 + labels2, loc="upper right", fontsize=9)
    ax.set_title("各渠道满意度对比", fontsize=14, fontweight="bold", pad=15)
    ax.grid(True, alpha=0.3, axis="y")
    return fig


# ==================== 渠道分析模块 ====================

def plot_channel_donut(chan_stats: pd.DataFrame) -> plt.Figure:
    """渠道占比环形图。"""
    fig, ax = plt.subplots(figsize=FIG_SIZE_SQUARE)
    channel_colors = {"在线": COLOR_INFO, "电话": COLOR_WARNING, "邮件": COLOR_SUCCESS}
    colors = [channel_colors.get(c, PALETTE_6[i % 6]) for i, c in enumerate(chan_stats["channel"])]

    wedges, texts, autotexts = ax.pie(
        chan_stats["ticket_count"], labels=chan_stats["channel"],
        autopct="%1.1f%%", startangle=90, pctdistance=0.78,
        colors=colors,
        wedgeprops={"width": 0.4, "edgecolor": "white", "linewidth": 1.5},
    )
    for t in autotexts:
        t.set_fontsize(9)
    for t in texts:
        t.set_fontsize(11)
    ax.set_title("渠道占比", fontsize=14, fontweight="bold", pad=15)
    return fig


def plot_channel_category_bar(cross_df: pd.DataFrame) -> plt.Figure:
    """渠道 × 分类分组柱状图。"""
    fig, ax = plt.subplots(figsize=(7, 4.5))
    cross_df.plot(kind="bar", ax=ax, color=PALETTE_6[:len(cross_df.columns)],
                  edgecolor="white", linewidth=0.8)
    ax.set_xlabel("渠道", fontsize=11)
    ax.set_ylabel("工单数量", fontsize=11)
    ax.set_title("渠道 × 分类 分布", fontsize=14, fontweight="bold", pad=15)
    ax.legend(title="分类", fontsize=8, ncol=2)
    ax.grid(True, alpha=0.3, axis="y")
    fig.autofmt_xdate(rotation=0)
    return fig


# ==================== 异常检测模块 ====================

def plot_anomaly_timeline(daily_df: pd.DataFrame, anomaly_df: pd.DataFrame) -> plt.Figure:
    """时间序列上标注异常点的图表。"""
    fig, ax = plt.subplots(figsize=FIG_SIZE_WIDE)
    dates = daily_df["date"].astype(str)

    ax.plot(dates, daily_df["ticket_count"].values,
            marker="o", color=COLOR_INFO, linewidth=2, markersize=6,
            label="每日工单量")

    vol_anomalies = anomaly_df[anomaly_df["anomaly_type"].str.contains("工单量", na=False)]
    confirmed = vol_anomalies[vol_anomalies["anomaly_level"].str.contains("确认", na=False)]
    suspected = vol_anomalies[vol_anomalies["anomaly_level"].str.contains("疑似", na=False)]

    if len(confirmed) > 0:
        for _, row in confirmed.iterrows():
            idx = daily_df[daily_df["date"] == row["date"]].index[0]
            ax.scatter(idx, row["ticket_count"], color=COLOR_DANGER,
                       s=150, zorder=5, marker="X", edgecolors="white", linewidth=1)
        ax.scatter([], [], color=COLOR_DANGER, s=100, marker="X",
                   edgecolors="white", linewidth=1, label="确认异常")

    if len(suspected) > 0:
        for _, row in suspected.iterrows():
            idx = daily_df[daily_df["date"] == row["date"]].index[0]
            ax.scatter(idx, row["ticket_count"], color=COLOR_WARNING,
                       s=100, zorder=5, marker="s", edgecolors="white", linewidth=1)
        ax.scatter([], [], color=COLOR_WARNING, s=100, marker="s",
                   edgecolors="white", linewidth=1, label="疑似异常")

    ax.set_xticks(range(len(dates)))
    ax.set_xticklabels(dates, rotation=45, ha="right")
    ax.set_ylabel("工单数量", fontsize=11)
    ax.set_title("异常检测时间线", fontsize=14, fontweight="bold", pad=15)
    ax.legend(fontsize=10, loc="upper left")
    ax.grid(True, alpha=0.3)
    return fig
