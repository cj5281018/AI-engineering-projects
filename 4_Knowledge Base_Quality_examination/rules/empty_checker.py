"""空答案检测器"""

from typing import Optional
from data.models import KBArticle, Issue
from config.settings import Settings


def check_empty(article: KBArticle) -> Optional[Issue]:
    """检测空答案或过短答案"""
    if not article.answer or article.answer.strip() == "":
        return Issue(
            article_id=article.id,
            type="empty_answer",
            detail=f"问题「{article.question}」的回答内容为空",
            severity="high",
            source="rule_engine",
            suggestion="请补充完整答案，确保覆盖用户关心的核心信息",
        )
    if len(article.answer.strip()) < Settings.INCOMPLETE_THRESHOLD:
        return Issue(
            article_id=article.id,
            type="incomplete",
            detail=(
                f"回答过短（{len(article.answer.strip())}字符），"
                f"可能遗漏关键信息"
            ),
            severity="low",
            source="rule_engine",
            suggestion="请补充更多细节，确保回答完整覆盖用户疑问",
        )
    return None
