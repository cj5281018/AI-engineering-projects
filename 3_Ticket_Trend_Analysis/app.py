"""
客服工单趋势分析 — Streamlit 交互式 Dashboard
==============================================
主入口：全局筛选器 + 侧边栏导航 + 7 个分析模块。
"""

import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt

from data_loader import load_data, filter_data, get_metadata
from analysis import (
    compute_kpi, daily_trend, daily_category_trend,
    category_stats, category_priority_cross,
    resolution_time_stats, satisfaction_stats,
    satisfaction_by_channel, channel_stats, channel_category_cross,
)
from anomaly_detector import generate_anomaly_report
from charts import (
    plot_category_donut, plot_priority_pie,
    plot_daily_volume_trend, plot_category_stacked_area,
    plot_priority_daily_trend, plot_category_bar,
    plot_category_priority_heatmap, plot_category_satisfaction,
    plot_resolution_time_bar, plot_priority_boxplot,
    plot_resolution_vs_satisfaction, plot_satisfaction_distribution,
    plot_satisfaction_by_channel, plot_channel_donut,
    plot_channel_category_bar, plot_anomaly_timeline,
)
from utils import fig_to_png_bytes, df_to_csv_bytes


# ==================== 页面配置 ====================

st.set_page_config(
    page_title="客服工单趋势分析 Dashboard",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.title("📊 客服工单趋势分析 Dashboard")
st.caption("基于 50 条工单数据的多维度分析和异常检测，帮助主管快速定位关键问题。")

# ==================== 加载数据 ====================

@st.cache_data
def get_full_data():
    """缓存全量数据加载。"""
    return load_data()

df_all = get_full_data()
meta = get_metadata(df_all)


# ==================== 侧边栏：导航 + 筛选器 ====================

with st.sidebar:
    st.header("🧭 导航")

    module = st.radio(
        "选择分析模块",
        options=[
            "📊 总览",
            "📈 时间趋势",
            "📂 分类分析",
            "⏱️ 处理效率",
            "😊 满意度分析",
            "🚨 异常检测",
            "📡 渠道分析",
        ],
        index=0,
    )

    st.divider()
    st.header("🔍 全局筛选器")

    # 日期范围
    date_min = df_all["date"].min()
    date_max = df_all["date"].max()
    date_range = st.date_input(
        "日期范围",
        value=(date_min, date_max),
        min_value=date_min,
        max_value=date_max,
    )

    # 统一处理 date_range 格式
    if isinstance(date_range, tuple) and len(date_range) == 2:
        start_date, end_date = date_range
    elif isinstance(date_range, (list,)) and len(date_range) == 2:
        start_date, end_date = date_range
    else:
        start_date, end_date = date_min, date_max

    # 分类
    categories = st.multiselect(
        "问题分类",
        options=sorted(df_all["category"].unique().tolist()),
        default=sorted(df_all["category"].unique().tolist()),
    )

    # 优先级
    priorities = st.multiselect(
        "优先级",
        options=["高", "中", "低"],
        default=["高", "中", "低"],
    )

    # 渠道
    channels = st.multiselect(
        "来源渠道",
        options=sorted(df_all["channel"].unique().tolist()),
        default=sorted(df_all["channel"].unique().tolist()),
    )

    st.divider()
    st.caption(f"数据范围: {meta['date_start']} ~ {meta['date_end']} ({meta['date_range_days']} 天)")
    st.caption(f"总工单数: {meta['total_tickets']}")


# ==================== 应用筛选器 ====================

df = filter_data(
    df_all,
    date_range=(start_date, end_date) if start_date and end_date else None,
    categories=categories if categories else None,
    priorities=priorities if priorities else None,
    channels=channels if channels else None,
)

if len(df) == 0:
    st.warning("⚠️ 当前筛选条件下无数据，请调整筛选器。")
    st.stop()


# ==================== 辅助函数 ====================

def show_chart(fig: plt.Figure, filename: str = "chart.png"):
    """显示图表并提供 PNG 下载按钮。"""
    st.pyplot(fig)
    col1, col2, col3 = st.columns([1, 1, 3])
    with col1:
        buf = fig_to_png_bytes(fig)
        st.download_button(
            label="📥 导出 PNG", data=buf,
            file_name=filename, mime="image/png",
            use_container_width=True,
        )


# ==================== 各模块渲染函数 ====================

def render_overview():
    """📊 总览模块。"""
    st.header("📊 总览仪表盘")

    kpi = compute_kpi(df)
    cat_stats_df = category_stats(df)
    top_cat = cat_stats_df.iloc[0]
    worst_cat = cat_stats_df.sort_values("avg_satisfaction").iloc[0]

    # 预构建第二分类文本（避免在 f-string 中对 pandas Series 做布尔判断）
    if len(cat_stats_df) > 1:
        top2 = cat_stats_df.iloc[1]
        top2_text = f"和「**{top2['category']}**」（{int(top2['ticket_count'])}条，占 {top2['pct']}%）"
        top2_pct = int(top_cat['ticket_count']) + int(top2['ticket_count'])
        top2_combined = f"，两类合计占总量 **{round(top2_pct / kpi['total_tickets'] * 100)}%**"
    else:
        top2_text = ""
        top2_combined = ""

    # === 文字概述（置顶） ===
    st.markdown(f"""
    ### 💡 分析概述

    当前筛选条件下共 **{kpi['total_tickets']}** 条工单，时间跨度 **{meta['date_start']} ~ {meta['date_end']}**（{meta['date_range_days']} 天）。

    **工单分布**：问题主要集中在「**{top_cat['category']}**」（{int(top_cat['ticket_count'])}条，占 {top_cat['pct']}%）{top2_text}{top2_combined}，符合帕累托法则——少数问题类型贡献了大部分工作量。

    **服务质量**：整体满意度均值 **{kpi['avg_satisfaction']:.2f}/5**，其中「{worst_cat['category']}」满意度最低（{worst_cat['avg_satisfaction']:.2f}/5），需重点关注。高优先级工单占比 **{kpi['high_priority_rate']:.1f}%**，说明整体服务压力较大。平均处理时长 **{kpi['avg_resolution_hours']:.1f}** 小时，未解决率 **{kpi['unresolved_rate']:.1f}%**。
    """)

    st.divider()

    # === KPI 卡片行 ===
    col1, col2, col3, col4, col5 = st.columns(5)
    with col1:
        st.metric("📋 工单总数", kpi["total_tickets"])
    with col2:
        st.metric("⭐ 平均满意度", f"{kpi['avg_satisfaction']:.2f} / 5")
    with col3:
        st.metric("⏱️ 平均处理时长", f"{kpi['avg_resolution_hours']:.1f} 小时")
    with col4:
        st.metric("❌ 未解决率", f"{kpi['unresolved_rate']:.1f}%",
                  delta=f"{kpi['unresolved_rate']:.1f}%",
                  delta_color="inverse" if kpi["unresolved_rate"] > 15 else "normal")
    with col5:
        st.metric("🔴 高优先级占比", f"{kpi['high_priority_rate']:.1f}%")

    st.divider()

    # === 图表区 ===
    col_left, col_right = st.columns(2)
    with col_left:
        fig = plot_category_donut(cat_stats_df)
        show_chart(fig, "category_donut.png")
    with col_right:
        fig = plot_priority_pie(df)
        show_chart(fig, "priority_pie.png")


def render_time_trend():
    """📈 时间趋势模块。"""
    st.header("📈 时间趋势分析")

    daily_df = daily_trend(df)
    daily_cat_df = daily_category_trend(df)

    peak_day = daily_df.loc[daily_df["ticket_count"].idxmax()]
    avg_daily = daily_df["ticket_count"].mean()
    peak_cat_day = daily_cat_df.sum(axis=1).idxmax()
    trend_direction = "上升" if daily_df["ticket_count"].iloc[-1] > daily_df["ticket_count"].iloc[0] else "平稳"

    # 检测是否有明显的单日突增
    max_count = daily_df["ticket_count"].max()
    spike_days = daily_df[daily_df["ticket_count"] >= avg_daily * 1.5]

    # === 文字概述（置顶） ===
    spike_text = ""
    if len(spike_days) > 0:
        spike_dates = ", ".join([str(d) for d in spike_days["date"].tolist()])
        spike_text = f"其中 **{spike_dates}** 工单量显著高于日均水平（≥{avg_daily * 1.5:.0f}条），可能存在突发因素。"

    st.markdown(f"""
    ### 💡 分析概述

    {meta['date_start']} ~ {meta['date_end']} 期间（共 {meta['date_range_days']} 天），日均工单量 **{avg_daily:.1f}** 条，整体趋势**{trend_direction}**。

    最高单日为 **{peak_day['date']}**（{int(peak_day['ticket_count'])} 条），其中高优先级 {int(peak_day['high_priority_count'])} 条。
    {spike_text}

    从分类堆叠面积图可以观察各分类的此消彼长：如某分类面积突然增大，说明该类问题在当日集中爆发。从优先级分面图可以判断高优先级工单是否随总量同步波动。
    """)

    st.divider()

    # === 图表区 ===
    st.subheader("每日工单量变化")
    fig = plot_daily_volume_trend(daily_df)
    show_chart(fig, "daily_volume_trend.png")

    st.subheader("各分类逐日分布")
    fig = plot_category_stacked_area(daily_cat_df)
    show_chart(fig, "category_stacked_area.png")

    st.subheader("各优先级日趋势")
    fig = plot_priority_daily_trend(daily_df, df)
    show_chart(fig, "priority_daily_trend.png")


def render_category_analysis():
    """📂 分类分析模块。"""
    st.header("📂 分类分析")

    cat_stats_df = category_stats(df)
    cross_df = category_priority_cross(df)
    top_cat = cat_stats_df.iloc[0]
    worst_sat_cat = cat_stats_df.sort_values("avg_satisfaction").iloc[0]
    worst_unresolved = cat_stats_df.sort_values("unresolved_rate", ascending=False).iloc[0]
    total = cat_stats_df["ticket_count"].sum()

    # 帕累托分析：前20%分类贡献了多少工单
    top_n = max(1, len(cat_stats_df) // 5)
    top_pct = cat_stats_df.head(top_n)["ticket_count"].sum() / total * 100

    # 热力图中高优先最集中的分类
    if "高" in cross_df.columns:
        high_priority_dense = cross_df["高"].idxmax()
        high_priority_val = cross_df["高"].max()
    else:
        high_priority_dense = "—"
        high_priority_val = 0

    # === 文字概述（置顶） ===
    st.markdown(f"""
    ### 💡 分析概述

    工单覆盖 **{len(cat_stats_df)}** 个分类，前 {top_n} 个分类贡献了 **{top_pct:.0f}%** 的工单量，验证了帕累托法则（少数问题类型占据多数工单）。

    **工单量最高**：「**{top_cat['category']}**」（{top_cat['ticket_count']} 条，占 {top_cat['pct']}%），平均处理时长 {top_cat['avg_resolution_hours']:.1f}h。
    **满意度最低**：「**{worst_sat_cat['category']}**」（{worst_sat_cat['avg_satisfaction']:.2f}/5），说明该分类的服务质量存在突出问题。
    **未解决率最高**：「**{worst_unresolved['category']}**」（{worst_unresolved['unresolved_rate']:.1f}%），存在严重积压风险。
    **高优先级最集中**：「**{high_priority_dense}**」分类中高优先级达 {int(high_priority_val)} 条，需优先投入资源。

    下方热力图展示各分类在不同优先级上的分布密度，颜色越深表示工单越集中。
    """)

    st.divider()

    # === 图表区 ===
    col_left, col_right = st.columns(2)
    with col_left:
        st.subheader("工单量排行")
        fig = plot_category_bar(cat_stats_df)
        show_chart(fig, "category_bar.png")
    with col_right:
        st.subheader("满意度对比")
        fig = plot_category_satisfaction(cat_stats_df)
        show_chart(fig, "category_satisfaction.png")

    st.subheader("分类 × 优先级交叉分析")
    fig = plot_category_priority_heatmap(cross_df)
    show_chart(fig, "category_priority_heatmap.png")

    with st.expander("📋 查看分类详细数据"):
        display_df = cat_stats_df.copy()
        display_df.columns = ["分类", "工单数", "平均满意度", "平均处理时长(h)", "高优先数", "未解决数", "占比%", "高优先率%", "未解决率%"]
        st.dataframe(display_df, use_container_width=True, hide_index=True)


def render_efficiency():
    """⏱️ 处理效率模块。"""
    st.header("⏱️ 处理效率分析")

    res_time_df = resolution_time_stats(df)
    slowest = res_time_df.iloc[0]
    fastest = res_time_df.iloc[-1]
    overall_avg = df["resolution_time_hours"].mean()

    # 计算超标工单（>48h）
    overdue = df[df["resolution_time_hours"] > 48]
    overdue_pct = len(overdue) / len(df) * 100

    # 按优先级计算
    high_avg = df[df["priority"] == "高"]["resolution_time_hours"].mean()
    low_avg = df[df["priority"] == "低"]["resolution_time_hours"].mean()

    # === 文字概述（置顶） ===
    st.markdown(f"""
    ### 💡 分析概述

    整体平均处理时长 **{overall_avg:.1f}** 小时（约 {overall_avg / 24:.1f} 天）。各类问题处理效率差异显著：

    - **最快**：「{fastest['category']}」平均仅 {fastest['avg_hours']:.1f}h，标准化程度高，适合优先纳入 AI 自动应答
    - **最慢**：「{slowest['category']}」平均 {slowest['avg_hours']:.1f}h（中位数 {slowest['median_hours']:.1f}h，最长 {slowest['max_hours']:.0f}h），是最大效率瓶颈

    高优先级工单平均处理 {high_avg:.1f}h，低优先级平均 {low_avg:.1f}h，说明优先级机制在实际处理中{'起到了区分作用' if high_avg < low_avg else '未起到预期的加速效果'}。

    有 **{len(overdue)}** 条工单处理时长超过 48 小时（占 {overdue_pct:.1f}%），属于超长工单，建议设置超时自动升级机制。

    下方散点图展示了处理时长与满意度的负相关关系：处理越久，满意度越低。
    """)

    st.divider()

    # === 图表区 ===
    col_left, col_right = st.columns(2)
    with col_left:
        st.subheader("各分类处理时长")
        fig = plot_resolution_time_bar(res_time_df)
        show_chart(fig, "resolution_time_bar.png")
    with col_right:
        st.subheader("优先级时长分布")
        fig = plot_priority_boxplot(df)
        show_chart(fig, "priority_boxplot.png")

    st.subheader("处理时长 vs 满意度关联")
    fig = plot_resolution_vs_satisfaction(df)
    show_chart(fig, "resolution_vs_satisfaction.png")


def render_satisfaction():
    """😊 满意度分析模块。"""
    st.header("😊 满意度分析")

    sat_stats = satisfaction_stats(df)
    sat_chan_df = satisfaction_by_channel(df)

    # 找出最好和最差的维度
    best_chan = sat_chan_df.sort_values("avg_satisfaction", ascending=False).iloc[0]
    worst_chan = sat_chan_df.sort_values("avg_satisfaction").iloc[0]
    low_tickets = df[df["satisfaction"] <= 2]

    # 已解决 vs 未解决 满意度
    resolved_sat = df[df["is_resolved"]]["satisfaction"].mean()
    unresolved_sat = df[~df["is_resolved"]]["satisfaction"].mean()

    # === 文字概述（置顶） ===
    st.markdown(f"""
    ### 💡 分析概述

    整体满意度均值 **{sat_stats['mean']:.2f}/5**，中位数 **{sat_stats['median']:.0f}**{'，低于行业常见水平（3.5+），说明整体服务质量有较大提升空间' if sat_stats['mean'] < 3.5 else ''}。

    **评分分布**：低分（≤2 分）工单 **{sat_stats['low_rate']}%**（{len(low_tickets)} 条），高分（≥4 分）仅 **{sat_stats['high_rate']}%**。满意度呈{'左偏分布，多数用户不满意' if sat_stats['mean'] < 3 else '较均匀分布'}。

    **渠道差异**：「{best_chan['channel']}」渠道满意度最高（{best_chan['avg_satisfaction']:.2f}/5），「{worst_chan['channel']}」渠道最低（{worst_chan['avg_satisfaction']:.2f}/5），低分率达 {worst_chan['low_satisfaction_rate'] * 100:.0f}%。

    **解决状态影响**：已解决工单满意度 {resolved_sat:.2f} vs 未解决 {unresolved_sat:.2f}，{'差距显著（' + str(abs(resolved_sat - unresolved_sat)) + '），将问题真正解决是提升满意度的关键' if abs(resolved_sat - unresolved_sat) > 0.5 else '差距不大'}。

    下方直方图展示满意度在各评分的分布密度，柱状图对比各渠道的双指标（平均满意度 vs 低分率）。
    """)

    st.divider()

    # === 图表区 ===
    st.metric("⭐ 整体满意度均值", f"{sat_stats['mean']:.2f} / 5",
              delta=f"低分率({sat_stats['low_rate']}%)")

    col_left, col_right = st.columns(2)
    with col_left:
        st.subheader("满意度分布")
        fig = plot_satisfaction_distribution(df)
        show_chart(fig, "satisfaction_distribution.png")
    with col_right:
        st.subheader("各渠道满意度")
        fig = plot_satisfaction_by_channel(sat_chan_df)
        show_chart(fig, "satisfaction_by_channel.png")


def _render_anomaly_card(anomaly: dict, index: int):
    """渲染单个异常卡片，展示详细信息。"""
    level = anomaly.get("level", "")
    is_confirmed = "确认" in level

    # 日期范围
    if "start_date" in anomaly:
        date_str = f"{anomaly['start_date']} → {anomaly['end_date']}（{anomaly.get('days', '?')}天）"
    elif "date" in anomaly:
        date_str = str(anomaly["date"])
    else:
        date_str = "—"

    # 卡片容器
    border_color = "#C44E52" if is_confirmed else "#E8A735"
    bg_color = "#FFF5F5" if is_confirmed else "#FFFCF0"

    card_html = f"""
    <div style="
        border-left: 4px solid {border_color};
        background: {bg_color};
        padding: 16px 20px;
        margin: 12px 0;
        border-radius: 6px;
    ">
        <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px;">
            <span style="font-size: 16px; font-weight: 700; color: #333;">
                {level} {anomaly.get('type', '')} #{index}
            </span>
            <span style="font-size: 13px; color: #888;">{date_str}</span>
        </div>
        <p style="font-size: 14px; color: #555; margin: 4px 0 12px 0;">
            {anomaly.get('description', '')}
        </p>
    </div>
    """
    st.markdown(card_html, unsafe_allow_html=True)

    # 判断依据
    evidence = anomaly.get("evidence", "")
    if evidence:
        with st.expander("📋 判断依据", expanded=True):
            st.markdown(evidence.replace("；", "\n- ").replace(":", "："))

    # 涉及工单
    ticket_ids = anomaly.get("related_ticket_ids", "")
    if ticket_ids:
        with st.expander("🎫 涉及工单", expanded=False):
            ids = [t.strip() for t in ticket_ids.split(",") if t.strip()]
            st.markdown(" ".join([f"`{tid}`" for tid in ids]))

    # 建议
    suggestion = anomaly.get("suggestion", "")
    if suggestion:
        st.info(f"💡 **建议行动**：{suggestion}")


def render_anomaly():
    """🚨 异常检测模块。"""
    st.header("🚨 异常检测")

    with st.expander("ℹ️ 检测机制说明", expanded=False):
        st.markdown("""
        采用 **三级递进检测** 机制：
        - **第一级**：Z-score（2σ）— 捕获显著偏离
        - **第二级**：7日滚动平均偏离（>30%）— 捕获渐进恶化
        - **第三级**：IQR 箱线图（1.5×IQR）— 鲁棒校验
        - **综合判定**：≥2 级命中 → 🔴 确认异常；1 级 → 🟡 疑似异常

        **额外规则**：
        - 连续 ≥3 天满意度下降 → 持续恶化预警
        - 某分类未解决率 > 整体均值 + 15% → 解决能力预警
        - 某分类单日占比 Z-score > 2σ 且 > 30% → 分类突增预警
        """)

    daily_df = daily_trend(df)
    daily_cat_df = daily_category_trend(df)

    report = generate_anomaly_report(df, daily_df, daily_cat_df)

    # === 文字概述（置顶） ===
    confirmed_list_preview = [a for a in report["all_anomalies"] if "确认" in a.get("level", "")]
    suspected_list_preview = [a for a in report["all_anomalies"] if "疑似" in a.get("level", "")]

    anomaly_narrative = ""
    if confirmed_list_preview:
        types = set(a["type"] for a in confirmed_list_preview)
        anomaly_narrative += f"确认异常 **{len(confirmed_list_preview)}** 个，类型包括：{'、'.join(types)}。"
    if suspected_list_preview:
        types = set(a["type"] for a in suspected_list_preview)
        anomaly_narrative += f"疑似异常 **{len(suspected_list_preview)}** 个，类型包括：{'、'.join(types)}。"
    if not confirmed_list_preview and not suspected_list_preview:
        anomaly_narrative = "当前数据范围内未检测到异常信号，系统运行正常。"

    st.markdown(f"""
    ### 💡 分析概述

    基于三级递进检测引擎（Z-score 2σ + 滚动平均偏离 30% + IQR 1.5×）和 3 项业务规则，对 {len(daily_df)} 天数据进行了全面扫描。

    {anomaly_narrative}

    每个异常卡片下方展开即可查看**判断依据**（具体触发条件）、**涉及工单**（精确定位到工单 ID）和**建议行动**（主管可直接执行的操作）。下方时间线图在时间轴上标注异常点位置，帮助主管快速定位问题时段。
    """)

    st.divider()

    # === 总结区 ===
    st.subheader("检测总结")
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("🔴 确认异常", report["confirmed_count"])
    with col2:
        st.metric("🟡 疑似异常", report["suspected_count"])
    with col3:
        st.metric("📋 检查维度", "6 项规则")
    with col4:
        st.metric("📊 检测天数", f"{len(daily_df)} 天")

    if report["summary"]:
        if report["confirmed_count"] > 0:
            st.error(f"⚠️ {report['summary']}")
        elif report["suspected_count"] > 0:
            st.warning(f"⚡ {report['summary']}")
        else:
            st.success(f"✅ {report['summary']}")

    st.divider()

    # === 异常卡片列表 ===
    all_anomalies = report["all_anomalies"]

    if all_anomalies:
        # 分组
        confirmed_list = [a for a in all_anomalies if "确认" in a.get("level", "")]
        suspected_list = [a for a in all_anomalies if "疑似" in a.get("level", "")]

        if confirmed_list:
            st.subheader(f"🔴 确认异常（{len(confirmed_list)} 个）")
            for i, anomaly in enumerate(confirmed_list, 1):
                _render_anomaly_card(anomaly, i)

        if suspected_list:
            st.subheader(f"🟡 疑似异常（{len(suspected_list)} 个）")
            for i, anomaly in enumerate(suspected_list, 1):
                _render_anomaly_card(anomaly, i)
    else:
        st.success("🎉 未发现任何异常信号，系统运行正常。")

    st.divider()

    # === 异常时间线图 ===
    st.subheader("📈 异常检测时间线")
    vol_detail = report["volume_detail"].copy()
    fig = plot_anomaly_timeline(daily_df, vol_detail)
    show_chart(fig, "anomaly_timeline.png")

    # === 三级检测明细（折叠） ===
    st.subheader("🔬 三级检测明细")
    col_left, col_right = st.columns(2)
    with col_left:
        with st.expander("📋 工单量异常逐日检测"):
            display_cols = {
                "date": "日期", "ticket_count": "工单量",
                "zscore_flag": "Z-score", "rolling_flag": "滚动偏离",
                "iqr_flag": "IQR", "hit_count": "命中数", "anomaly_level": "判定",
            }
            st.dataframe(
                vol_detail[[c for c in display_cols if c in vol_detail.columns]]
                .rename(columns=display_cols),
                use_container_width=True, hide_index=True,
            )
    with col_right:
        with st.expander("📋 满意度异常逐日检测"):
            sat_detail = report["satisfaction_detail"].copy()
            display_cols = {
                "date": "日期", "avg_satisfaction": "平均满意度",
                "zscore_flag": "Z-score", "rolling_flag": "滚动偏离",
                "iqr_flag": "IQR", "hit_count": "命中数", "anomaly_level": "判定",
            }
            st.dataframe(
                sat_detail[[c for c in display_cols if c in sat_detail.columns]]
                .rename(columns=display_cols),
                use_container_width=True, hide_index=True,
            )

    # === CSV 导出 ===
    if all_anomalies:
        st.divider()
        col1, col2 = st.columns([1, 4])
        with col1:
            anomalies_df = pd.DataFrame(all_anomalies)
            csv_buf = df_to_csv_bytes(anomalies_df)
            st.download_button(
                label="📥 导出异常报告 CSV",
                data=csv_buf,
                file_name="anomaly_report.csv",
                mime="text/csv",
            )


def render_channel():
    """📡 渠道分析模块。"""
    st.header("📡 渠道分析")

    chan_stats_df = channel_stats(df)
    cross_df = channel_category_cross(df)

    best_chan = chan_stats_df.sort_values("avg_satisfaction", ascending=False).iloc[0]
    worst_chan = chan_stats_df.sort_values("avg_satisfaction").iloc[0]
    most_chan = chan_stats_df.sort_values("ticket_count", ascending=False).iloc[0]

    # 各渠道主要问题类型
    chan_focus = {}
    for ch in cross_df.index:
        top_cat = cross_df.loc[ch].idxmax()
        chan_focus[ch] = (top_cat, cross_df.loc[ch, top_cat])

    # === 文字概述（置顶） ===
    focus_lines = ""
    for ch, (cat, n) in chan_focus.items():
        focus_lines += f"- 「**{ch}**」渠道以 **{cat}** 为主（{n} 条），占该渠道 {n / chan_stats_df[chan_stats_df['channel'] == ch]['ticket_count'].values[0] * 100:.0f}%\n"

    chan_count = len(chan_stats_df)
    st.markdown(f"""
    ### 💡 分析概述

    工单来自 **{chan_count}** 个渠道，其中「**{most_chan['channel']}**」渠道占比最高（{most_chan['ticket_count']} 条，{most_chan['pct']}%）。

    **各渠道主要问题**：
    {focus_lines}
    **服务质量对比**：「{best_chan['channel']}」满意度最高（{best_chan['avg_satisfaction']:.2f}/5），「{worst_chan['channel']}」满意度最低（{worst_chan['avg_satisfaction']:.2f}/5），处理时长 {worst_chan['avg_resolution_hours']:.1f}h，{'可能需要增加该渠道的人力配置' if worst_chan['avg_resolution_hours'] > chan_stats_df['avg_resolution_hours'].mean() else '效率正常'}。

    下方分组柱状图展示各渠道内不同分类的工单分布，帮助判断是否需要针对特定渠道优化某类问题的处理流程。
    """)

    st.divider()

    # === 图表区 ===
    col_left, col_right = st.columns(2)
    with col_left:
        st.subheader("渠道占比")
        fig = plot_channel_donut(chan_stats_df)
        show_chart(fig, "channel_donut.png")
    with col_right:
        st.subheader("渠道 × 分类分布")
        fig = plot_channel_category_bar(cross_df)
        show_chart(fig, "channel_category_bar.png")

    st.subheader("渠道综合对比")
    display_df = chan_stats_df.copy()
    display_df.columns = ["渠道", "工单数", "平均满意度", "平均处理时长(h)", "未解决率%", "占比%"]
    st.dataframe(display_df, use_container_width=True, hide_index=True)


# ==================== 模块路由 ====================

MODULE_MAP = {
    "📊 总览": render_overview,
    "📈 时间趋势": render_time_trend,
    "📂 分类分析": render_category_analysis,
    "⏱️ 处理效率": render_efficiency,
    "😊 满意度分析": render_satisfaction,
    "🚨 异常检测": render_anomaly,
    "📡 渠道分析": render_channel,
}

# 渲染当前选中的模块
render_func = MODULE_MAP.get(module)
if render_func:
    render_func()

# ==================== 页脚 ====================

st.divider()
st.caption(
    "🔧 工单趋势分析工具 | 基于 Python + Streamlit + Matplotlib + Seaborn | "
    f"数据范围: {meta['date_start']} ~ {meta['date_end']}"
)
