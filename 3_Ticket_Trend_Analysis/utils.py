"""
工具函数模块：导出、配色常量、样式设置。
"""

from io import BytesIO

import pandas as pd
import matplotlib.pyplot as plt
from matplotlib.figure import Figure


# ==================== 配色方案 ====================

PALETTE_6 = ["#4C72B0", "#55A868", "#C44E52", "#8172B2", "#CCB974", "#64B5CD"]

PRIORITY_COLORS = {"高": "#C44E52", "中": "#E8A735", "低": "#55A868"}

COLOR_DANGER = "#C44E52"
COLOR_WARNING = "#E8A735"
COLOR_SUCCESS = "#55A868"
COLOR_INFO = "#4C72B0"

SEABORN_STYLE = "whitegrid"
FIGURE_DPI = 120


def set_style():
    """统一设置 Matplotlib/Seaborn 样式。"""
    import seaborn as sns
    sns.set_style(SEABORN_STYLE)
    plt.rcParams.update({
        "figure.dpi": FIGURE_DPI,
        "savefig.dpi": FIGURE_DPI,
        "savefig.bbox": "tight",
        "savefig.pad_inches": 0.1,
    })


def fig_to_png_bytes(fig: Figure) -> BytesIO:
    """将 Matplotlib Figure 转换为 PNG 字节流。"""
    buf = BytesIO()
    fig.savefig(buf, format="png", dpi=FIGURE_DPI, bbox_inches="tight")
    buf.seek(0)
    return buf


def df_to_csv_bytes(df: pd.DataFrame) -> BytesIO:
    """将 DataFrame 转换为 CSV 字节流（UTF-8 BOM，兼容 Excel 中文打开）。"""
    buf = BytesIO()
    df.to_csv(buf, index=False, encoding="utf-8-sig")
    buf.seek(0)
    return buf
