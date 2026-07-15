"""重复条目检测器

两级检测:
1. 精确重复: question 字段完全一致
2. 模糊重复: Jaccard 相似度超过阈值
"""

import re
from data.models import KBArticle, Issue
from config.settings import Settings


def check_duplicates(articles: list[KBArticle]) -> list[Issue]:
    """检测所有条目中的重复问题"""
    issues: list[Issue] = []

    for i in range(len(articles)):
        for j in range(i + 1, len(articles)):
            a, b = articles[i], articles[j]

            # 精确重复检测
            if _is_exact_duplicate(a, b):
                # 判断保留哪个（取更新时间更新的）
                keeper = a if a.updated_at >= b.updated_at else b
                remover = b if keeper is a else a
                issues.append(Issue(
                    article_id=a.id,
                    type="duplicate",
                    detail=(
                        f"与 {b.id}「{b.question}」问题完全重复"
                    ),
                    severity="medium",
                    source="rule_engine",
                    suggestion=(
                        f"建议合并：保留 {keeper.id}（更新于 {keeper.updated_at}），"
                        f"删除 {remover.id}（更新于 {remover.updated_at}）"
                    ),
                    related_articles=[b.id],
                ))

                # 如果答案不同，同时标记为内部矛盾
                if a.answer.strip() != b.answer.strip():
                    issues.append(Issue(
                        article_id=a.id,
                        type="contradictory_internal",
                        detail=(
                            f"与 {b.id} 问题相同（「{a.question}」），"
                            f"但答案不同\n"
                            f"  {a.id}: {a.answer[:50]}...\n"
                            f"  {b.id}: {b.answer[:50]}..."
                        ),
                        severity="high",
                        source="rule_engine",
                        suggestion=(
                            f"统一说法：以 {keeper.id} 为准，"
                            f"修正或删除 {remover.id}"
                        ),
                        related_articles=[b.id],
                    ))

            # 模糊重复检测（仅在非精确重复时）
            elif _is_fuzzy_duplicate(a, b):
                similarity = _jaccard_similarity(
                    set(_tokenize(a.question)),
                    set(_tokenize(b.question)),
                )
                if similarity >= Settings.DUPLICATE_SIMILARITY_THRESHOLD:
                    issues.append(Issue(
                        article_id=a.id,
                        type="duplicate",
                        detail=(
                            f"与 {b.id}「{b.question}」问题高度相似"
                            f"（相似度 {similarity:.0%}）"
                        ),
                        severity="low",
                        source="rule_engine",
                        suggestion="建议确认是否为重复条目，如是则合并",
                        related_articles=[b.id],
                    ))

    return issues


def _is_exact_duplicate(a: KBArticle, b: KBArticle) -> bool:
    """检测问题文本是否完全一致（去除标点和空格后）"""
    return _normalize(a.question) == _normalize(b.question)


def _is_fuzzy_duplicate(a: KBArticle, b: KBArticle) -> bool:
    """判断是否值得做模糊匹配（同category或含相同关键词）"""
    if a.category == b.category:
        return True
    # 提取核心词判断是否有交集
    tokens_a = set(_tokenize(a.question))
    tokens_b = set(_tokenize(b.question))
    return len(tokens_a & tokens_b) >= 2


def _normalize(text: str) -> str:
    """标准化：去标点、去空格、转小写"""
    text = re.sub(r"[^\w]", "", text)
    return text.lower().strip()


def _tokenize(text: str) -> list[str]:
    """简单分词：按非文字符分割"""
    # 对于中文，按字符分割；对于英文，按空格分割
    text = re.sub(r"[^\w一-鿿]", "", text)
    # 逐字符分割中文部分
    tokens = []
    for char in text:
        if '一' <= char <= '鿿':
            tokens.append(char)
        else:
            tokens.append(char)
    return [t for t in tokens if t.strip()]


def _jaccard_similarity(set_a: set, set_b: set) -> float:
    """计算 Jaccard 相似度"""
    if not set_a and not set_b:
        return 1.0
    intersection = set_a & set_b
    union = set_a | set_b
    return len(intersection) / len(union) if union else 0.0
