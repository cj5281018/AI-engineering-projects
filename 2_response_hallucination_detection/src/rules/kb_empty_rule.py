"""规则1：知识库空检测 — 检测能力越界

当 knowledge_base 为空时，如果回复中包含具体的物流/订单/退款等信息，
说明系统在假装具备不具备的能力。
"""

import re
from typing import Dict, Any, Optional
from .base_rule import BaseRule


class KBEmptyRule(BaseRule):
    """检测知识库为空时回复是否虚构信息"""

    # 回复中包含具体信息的检测模式
    CONCRETE_INFO_PATTERNS = [
        r'查到了',
        r'您的包裹',
        r'在\S+转运中心',
        r'预计.*送达',
        r'预计.*到账',
        r'退款.*处理中',
        r'已帮您修改',
        r'已为您修改',
        r'已升级',
        r'工单.*升级',
        r'专属客服.*联系',
        r'\d+小时内',
        r'\d+天.*到',
    ]

    def __init__(self):
        super().__init__(
            name="KB-Empty",
            description="知识库为空时，回复是否包含具体信息（能力越界检测）"
        )

    def detect(self, reply: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        kb = reply.get("knowledge_base", "").strip()
        system_reply = reply.get("system_reply", "")

        # 知识库非空，此规则不适用
        if kb not in ("无", "无（客服系统未接入物流查询接口）",
                       "无（客服系统未接入退款进度查询接口）",
                       "无（客服系统未接入订单修改接口，需人工后台操作）",
                       "无（客服系统不具备工单升级功能，需转人工处理）"):
            # 放宽条件：只要以"无"开头就认为是空 KB
            if not kb.startswith("无"):
                return None

        # 检查回复中是否包含具体的操作结果或信息
        matched_patterns = []
        for pattern in self.CONCRETE_INFO_PATTERNS:
            if re.search(pattern, system_reply):
                matched_patterns.append(pattern)

        if matched_patterns:
            return {
                "is_hallucination": True,
                "confidence": 0.92,
                "rule_name": self.name,
                "evidence": f"知识库为空，但回复中包含了具体信息（匹配模式：{', '.join(matched_patterns)}），"
                            f"属于能力越界型幻觉",
            }

        return None
