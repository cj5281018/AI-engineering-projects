"""
Faithfulness (事实忠实性) 评估模块

方法论来源: RAGAS Faithfulness
- https://docs.ragas.io/en/latest/concepts/metrics/faithfulness.html
- 将回复拆解为原子性陈述(claims)，逐条验证是否可被常识或问题上下文支持

本模块定义评分 Prompt 和辅助函数，供 llm_judge.py 调用。
"""

# RAGAS Faithfulness 风格的评分 Prompt (嵌入到 llm judge system prompt 中)
F_SYSTEM_PROMPT_FRAGMENT = """
## Faithfulness (事实忠实性) — 评分指南
将自动回复拆解为独立的陈述句，逐条判断是否可被以下信息支持:
1. 通用常识 (如"退款一般 1-3 个工作日"是常识)
2. 用户问题上下文中隐含的信息 (如用户说"才买三天"暗示在质保期内)

计算方法: Faithfulness = 可验证的陈述数 / 总陈述数
- 1.0 (5分): 所有陈述都事实正确
- 0.8 (4分): 大部分正确，有轻微不精确
- 0.6 (3分): 部分笼统但无明显错误
- 0.4 (2分): 存在明显事实错误
- 0.2 (1分): 虚构信息或严重错误
"""


def extract_claims(reply: str) -> list[str]:
    """
    将回复拆解为原子性陈述句。
    使用简单的句号/分号拆分，后续可升级为依赖解析。

    Args:
        reply: 自动回复文本

    Returns:
        原子性陈述列表
    """
    import re
    # 按句号、分号、感叹号拆分
    sentences = re.split(r'[。；;！!]', reply)
    claims = [s.strip() for s in sentences if len(s.strip()) > 4]
    return claims if claims else [reply]
