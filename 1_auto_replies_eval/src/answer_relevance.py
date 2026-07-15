"""
Answer Relevance (答案相关性) 评估模块

方法论来源: RAGAS Answer Relevance
- https://docs.ragas.io/en/stable/concepts/metrics/available_metrics/index.md
- 衡量生成答案是否切题地回应了输入问题

本模块定义评分 Prompt 和辅助函数。
"""

# RAGAS Answer Relevance 风格的评分 Prompt
A_SYSTEM_PROMPT_FRAGMENT = """
## Answer Relevance (答案相关性) — 评分指南
评估回复是否直接回应了用户的问题。考虑:
1. 回复是否覆盖了用户的核心诉求?
2. 是否有大量无关或偏离的内容?
3. 用户能否从回复中得到他们正在寻找的信息?

评分标准:
- 5 = 完全切题，精确回应用户每一个问题点
- 4 = 基本切题，覆盖了核心诉求
- 3 = 部分相关，但有一些无关或偏离内容
- 2 = 边缘相关，回答偏离了核心问题
- 1 = 完全不相关，答非所问

注意: 给出通用模板但方向正确的回复应打 3 分，方向偏了的打 2 分。
"""
