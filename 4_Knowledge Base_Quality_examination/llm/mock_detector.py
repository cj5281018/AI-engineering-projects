"""Mock 模式 LLM 检测器

针对已知的 40 条数据预设返回结果，格式与真实 API 模式完全一致。
"""

from typing import Optional
from data.models import KBArticle, Issue
from llm.base import LLMDetector

# 预设的 Mock 检测结果
MOCK_RESULTS: dict[str, list[dict]] = {
    "KB031": [
        {
            "type": "unprofessional",
            "detail": (
                "回答「这个我们不管理哦」语气推诿，缺乏服务意识。"
                "虽然内容本身是让用户联系支付平台，但表达方式容易引起不满。"
            ),
            "severity": "medium",
            "suggestion": (
                "改为更专业的表达，例如："
                "「支付密码属于支付平台管理，建议您直接联系微信或支付宝客服找回密码。"
                "如果您需要我帮您转接到对应平台，请告诉我。」"
            ),
        }
    ],
    "KB016": [
        {
            "type": "outdated",
            "detail": (
                "条目说在线客服「7x24小时全天候服务」，"
                "但当前业务规则明确在线客服时间为9:00-22:00，并非24小时。"
            ),
            "severity": "medium",
            "suggestion": "将在线客服时间修改为「9:00-22:00」，并补充邮件客服渠道",
        },
        {
            "type": "missing_coverage",
            "detail": "业务规则中有「邮件客服：24小时内回复」的渠道，但知识库中没有相关条目覆盖",
            "severity": "medium",
            "suggestion": "新增关于邮件客服的FAQ条目，说明邮箱地址和回复时效",
        },
    ],
    "KB010": [
        {
            "type": "outdated",
            "detail": (
                "条目说支持「电子发票和纸质发票」，且申请方式为「下单时在备注中填写」。"
                "但当前业务规则为仅支持电子发票，纸质发票已取消，"
                "申请方式改为在订单详情页申请。"
            ),
            "severity": "medium",
            "suggestion": (
                "修改为：「支持电子发票，可在订单详情页申请。"
                "目前不支持纸质发票。」"
            ),
        }
    ],
    "KB011": [
        {
            "type": "outdated",
            "detail": (
                "条目提到「我们会随货寄出纸质发票」，"
                "但当前业务规则已取消纸质发票，仅支持电子发票。"
            ),
            "severity": "medium",
            "suggestion": (
                "修改为：「我们支持电子发票，可在订单详情页申请。"
                "目前不支持纸质发票。」"
            ),
        }
    ],
    "KB001": [
        {
            "type": "contradictory_internal",
            "detail": (
                "与KB002说法矛盾。KB001说非质量问题退货运费由买家承担，"
                "但KB002说所有退货运费都由商家承担。"
            ),
            "severity": "high",
            "suggestion": "统一说法：以KB001为准（符合业务规则），修改KB002",
        }
    ],
}


class MockLLMDetector(LLMDetector):
    """Mock 模式：返回预设结果"""

    def __init__(self):
        self._results = MOCK_RESULTS

    def analyze_article(
        self, article: KBArticle, rules_text: str = ""
    ) -> list[Issue]:
        """返回预设的检测结果"""
        raw_issues = self._results.get(article.id, [])
        return [
            Issue(
                article_id=article.id,
                type=ri["type"],
                detail=ri["detail"],
                severity=ri["severity"],
                source="llm",
                suggestion=ri.get("suggestion"),
            )
            for ri in raw_issues
        ]

    def check_semantic_contradiction(
        self, article_a: KBArticle, article_b: KBArticle
    ) -> Optional[Issue]:
        """Mock 模式下预设的条目间矛盾检测"""
        # 预设KB001与KB002存在矛盾
        if "KB001" in (article_a.id, article_b.id) and "KB002" in (article_a.id, article_b.id):
            return Issue(
                article_id=article_a.id,
                type="contradictory_internal",
                detail=(
                    f"与 {article_b.id} 在退货运费承担方上存在矛盾。"
                    f"{article_a.id}说非质量问题由买家承担，"
                    f"但{article_b.id}说所有运费都由商家承担。"
                ),
                severity="high",
                source="llm",
                suggestion="统一退货运费政策说法，以业务规则为准",
                related_articles=[article_b.id],
            )
        return None

    def suggest_improvement(
        self, article: KBArticle, issues: list[Issue]
    ) -> str:
        """返回预设的改进建议"""
        if article.id in self._results:
            issues_data = self._results[article.id]
            suggestions = [ri.get("suggestion", "") for ri in issues_data]
            return "\n".join(s for s in suggestions if s)
        return "条目内容与业务规则一致，无需修改。"
