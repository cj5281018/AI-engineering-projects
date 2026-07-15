"""LLM 检测器抽象接口"""

from abc import ABC, abstractmethod
from typing import Optional
from data.models import KBArticle, Issue, BusinessRule


class LLMDetector(ABC):
    """LLM 检测器的抽象基类"""

    @abstractmethod
    def analyze_article(
        self, article: KBArticle, rules_text: str
    ) -> list[Issue]:
        """分析单条知识库条目质量，返回检测到的问题列表"""
        ...

    @abstractmethod
    def check_semantic_contradiction(
        self, article_a: KBArticle, article_b: KBArticle
    ) -> Optional[Issue]:
        """检测两条条目间是否存在语义矛盾"""
        ...

    @abstractmethod
    def suggest_improvement(
        self, article: KBArticle, issues: list[Issue]
    ) -> str:
        """根据问题生成改进建议"""
        ...
