"""数据模型定义：KB条目、业务规则、检测结果Issue等核心数据结构"""

from dataclasses import dataclass, field
from typing import Optional


@dataclass
class KBArticle:
    """单条知识库FAQ条目"""
    id: str
    question: str
    answer: str
    category: str
    created_at: str
    updated_at: str

    @classmethod
    def from_dict(cls, d: dict) -> "KBArticle":
        return cls(
            id=d["id"],
            question=d["question"],
            answer=d.get("answer", ""),
            category=d.get("category", ""),
            created_at=d.get("created_at", ""),
            updated_at=d.get("updated_at", ""),
        )


@dataclass
class RuleItem:
    """单条业务规则"""
    field: str                         # 规则字段标识
    description: str                   # 原始文本
    key: str = ""                      # 结构化键
    value: object = None               # 结构化值
    rule_type: str = "text"            # numeric / boolean / enum / text


@dataclass
class BusinessRule:
    """一个主题下的业务规则集合"""
    topic: str                         # 主题名称
    rules: list[RuleItem] = field(default_factory=list)


@dataclass
class Issue:
    """检测到的问题"""
    article_id: str                    # KB ID
    type: str                          # 问题类型
    detail: str                        # 具体描述
    severity: str = "medium"           # high / medium / low
    source: str = "rule_engine"        # rule_engine / llm
    expected: Optional[str] = None     # 期望的正确内容
    suggestion: Optional[str] = None   # 改进建议
    related_articles: Optional[list[str]] = None  # 关联条目ID


@dataclass
class GovernanceAction:
    """治理建议"""
    action: str                        # update / merge / delete / create / improve
    summary: str                       # 建议摘要
    priority: str = "P2"               # P0 / P1 / P2
    detail: str = ""                   # 详细建议


@dataclass
class DetectionResult:
    """单条条目的完整检测结果"""
    article: KBArticle
    issues: list[Issue] = field(default_factory=list)
    governance: Optional[GovernanceAction] = None
