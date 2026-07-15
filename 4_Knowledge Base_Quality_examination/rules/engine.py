"""规则引擎主调度器

编排所有确定性检测器，统一产出检测结果。
"""

from data.models import KBArticle, Issue
from rules.parser import parse_business_context
from rules.outdated_checker import check_outdated
from rules.empty_checker import check_empty
from rules.duplicate_checker import check_duplicates
from rules.contradiction_checker import check_contradictions


class RuleEngine:
    """规则引擎：处理所有确定性检测"""

    def __init__(self, business_context_text: str):
        self.business_rules = parse_business_context(business_context_text)

    def run(self, articles: list[KBArticle]) -> list[Issue]:
        """运行全部检测，返回 Issue 列表"""
        issues: list[Issue] = []

        # 1. 逐条检测过时/矛盾
        for article in articles:
            outdated_issues = check_outdated(article, self.business_rules)
            issues.extend(outdated_issues)

            # 空答案检测
            empty_issue = check_empty(article)
            if empty_issue:
                issues.append(empty_issue)

        # 2. 跨条目检测重复
        dup_issues = check_duplicates(articles)
        issues.extend(dup_issues)

        # 3. 跨条目检测内部矛盾
        contra_issues = check_contradictions(articles)
        # 避免重复（已在 duplicate_checker 中标记了重复条目的矛盾）
        existing_keys = {(i.article_id, i.type) for i in issues}
        for ci in contra_issues:
            if (ci.article_id, ci.type) not in existing_keys:
                issues.append(ci)

        return issues
