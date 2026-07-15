"""规则2：数值矛盾检测 — 检测参数编造和政策编造

从 knowledge_base 和 system_reply 中提取数值+单位组合，比较是否存在矛盾。
"""

from typing import Dict, Any, Optional, List
from .base_rule import BaseRule
from ..utils.text_utils import extract_numeric_claims, compare_numeric_values


class NumericConflictRule(BaseRule):
    """检测知识库和回复之间的数值矛盾"""

    def __init__(self):
        super().__init__(
            name="Numeric-Conflict",
            description="提取数值+单位组合，检测知识库与回复之间的数值矛盾"
        )

    def detect(self, reply: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        kb = reply.get("knowledge_base", "")
        system_reply = reply.get("system_reply", "")

        kb_claims = extract_numeric_claims(kb)
        reply_claims = extract_numeric_claims(system_reply)

        if not kb_claims or not reply_claims:
            return None

        contradictions = []
        for rc in reply_claims:
            for kc in kb_claims:
                if rc['category'] == kc['category']:
                    if compare_numeric_values(rc['value'], kc['value']):
                        contradictions.append({
                            'reply_value': rc['value'],
                            'reply_type': rc['type'],
                            'kb_value': kc['value'],
                            'kb_type': kc['type'],
                            'category': rc['category'],
                        })

        if contradictions:
            confidence = min(0.75 + 0.05 * len(contradictions), 0.90)
            evidence_items = [
                f"回复说「{c['reply_value']}」，但知识库是「{c['kb_value']}」"
                for c in contradictions
            ]
            return {
                "is_hallucination": True,
                "confidence": confidence,
                "rule_name": self.name,
                "evidence": "数值矛盾：" + "；".join(evidence_items),
                "contradictions": contradictions,
            }

        return None
