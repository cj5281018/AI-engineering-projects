"""规则抽象基类"""

from abc import ABC, abstractmethod
from typing import Dict, Any, Optional


class BaseRule(ABC):
    """所有规则的抽象基类"""

    def __init__(self, name: str, description: str = ""):
        self.name = name
        self.description = description

    @abstractmethod
    def detect(self, reply: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        对单条回复执行检测。

        Args:
            reply: 包含 user_question, system_reply, knowledge_base 的字典

        Returns:
            如果规则触发，返回检测结果字典，包含：
                - is_hallucination: bool
                - confidence: float (0-1)
                - rule_name: str
                - evidence: str
            如果规则未触发，返回 None
        """
        pass

    def __call__(self, reply: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        return self.detect(reply)
