"""条目间矛盾检测器

按 category 分组，对同一主题下的条目提取关键断言进行两两对比，
检测是否存在内部矛盾。
"""

import re
from typing import Optional
from data.models import KBArticle, Issue

# 定义每组断言提取规则: (断言主题, 正则模式, 提取函数)
ASSERTION_RULES: list[tuple[str, str, callable]] = [
    # 运费承担方
    ("运费承担方", r"(运费|退货运费).*?(买家|商家|平台|我们).*?(承担|出|付)",
     lambda m: m.group(2) if m.group(2) else None),
    # 退货天数
    ("退货天数", r"(\d+)\s*天无理由",
     lambda m: m.group(1)),
    # 是否有某项服务
    ("是否支持", r"(支持|可以|有|提供).*(货到付款|纸质发票|电子发票|分期|换货|价保)",
     lambda m: "支持"),
    # 审核时间
    ("审核时间", r"(\d+)[-~到]\s*(\d+)\s*个工作日",
     lambda m: f"{m.group(1)}-{m.group(2)}"),
]


def check_contradictions(articles: list[KBArticle]) -> list[Issue]:
    """检测同一主题下条目间的矛盾"""
    # 按 category 分组
    grouped: dict[str, list[KBArticle]] = {}
    for article in articles:
        grouped.setdefault(article.category, []).append(article)

    issues: list[Issue] = []
    for category, group in grouped.items():
        if len(group) < 2:
            continue

        # 两两对比同组条目
        for i in range(len(group)):
            for j in range(i + 1, len(group)):
                a, b = group[i], group[j]
                contradictions = _compare_articles(a, b)
                issues.extend(contradictions)

    return issues


def _compare_articles(a: KBArticle, b: KBArticle) -> list[Issue]:
    """比较两条条目是否存在矛盾"""
    issues: list[Issue] = []

    for topic, pattern, extractor in ASSERTION_RULES:
        value_a = _extract_assertion(a.answer, pattern, extractor)
        value_b = _extract_assertion(b.answer, pattern, extractor)

        if value_a is None or value_b is None:
            continue  # 至少有一条未提及此主题，跳过

        if value_a != value_b:
            issues.append(Issue(
                article_id=a.id,
                type="contradictory_internal",
                detail=(
                    f"与 {b.id} 在「{topic}」上说法矛盾\n"
                    f"  {a.id}: 「{_snippet(a.answer, 30)}」\n"
                    f"  {b.id}: 「{_snippet(b.answer, 30)}」"
                ),
                severity="high",
                source="rule_engine",
                suggestion=f"统一关于「{topic}」的说法，确保信息一致",
                related_articles=[b.id],
            ))

    return issues


def _extract_assertion(
    text: str, pattern: str, extractor: callable
) -> Optional[str]:
    """从文本中提取断言值"""
    m = re.search(pattern, text)
    if m:
        return extractor(m)
    return None


def _snippet(text: str, max_len: int = 30) -> str:
    """截取文本片段"""
    if len(text) <= max_len:
        return text
    return text[:max_len] + "..."
