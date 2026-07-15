"""规则3：关键词否定检测 — 检测信息编造和参数编造

检测知识库中包含否定表述（未标注、不支持、无）而回复中使用肯定表述的模式。
"""

import re
from typing import Dict, Any, Optional
from .base_rule import BaseRule


class KeywordNegationRule(BaseRule):
    """检测知识库否定关键词与回复肯定表述的矛盾"""

    # 否定关键词 → 对应的肯定表述模式（正则）
    NEGATION_PAIRS = [
        {
            "neg_keywords": ["未标注NFC", "未标注 NFC", "未标注nfc"],
            "affirm_patterns": [
                r'支持NFC', r'有NFC', r'带NFC', r'支持 NFC',
                r'公交卡.*门禁卡.*移动支付',
            ],
            "category": "参数编造",
        },
        {
            "neg_keywords": ["未提及其他品牌", "未提及.*品牌关联", "无.*品牌.*关联"],
            "affirm_patterns": [
                r'旗下.*子品牌', r'是一家', r'同一.*集团', r'共享.*供应链',
                r'XX品牌旗下',
            ],
            "category": "信息编造",
        },
        {
            "neg_keywords": ["无学生优惠", "无.*学生.*政策"],
            "affirm_patterns": [
                r'学生优惠', r'学生证.*9折', r'学生.*认证', r'学生价',
                r'9折', r'凭学生证',
            ],
            "category": "政策编造",
        },
    ]

    def __init__(self):
        super().__init__(
            name="Keyword-Negation",
            description="检测知识库否定关键词与回复肯定表述的矛盾"
        )

    def detect(self, reply: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        kb = reply.get("knowledge_base", "")
        system_reply = reply.get("system_reply", "")

        for pair in self.NEGATION_PAIRS:
            # 检查知识库中是否有否定关键词
            neg_matched = False
            for neg_kw in pair["neg_keywords"]:
                if re.search(neg_kw, kb):
                    neg_matched = True
                    break

            if not neg_matched:
                continue

            # 检查回复中是否有对应肯定表述
            for pattern in pair["affirm_patterns"]:
                if re.search(pattern, system_reply):
                    return {
                        "is_hallucination": True,
                        "confidence": 0.70,
                        "rule_name": self.name,
                        "evidence": f"知识库包含否定表述，但回复做了肯定陈述（匹配：{pattern}），"
                                    f"归为{pair['category']}",
                        "negation_pair": pair,
                    }

        # 特殊规则：知识库中有成分警告，回复说放心使用
        harmful_ingredients = ['视黄醇', '烟酰胺', '视黄醇棕榈酸酯']
        kb_has_warning = any(ing in kb for ing in harmful_ingredients) and '孕妇' in kb
        if kb_has_warning:
            if re.search(r'孕妇.*放心|可以放心.*使用|孕妈.*回购', system_reply):
                return {
                    "is_hallucination": True,
                    "confidence": 0.75,
                    "rule_name": self.name + "-Safety",
                    "evidence": f"知识库标注了含慎用成分并建议咨询医生，但回复却说可以放心使用，"
                                f"属于安全误导",
                }

        return None
