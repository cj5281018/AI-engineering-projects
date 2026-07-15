"""规则与 LLM 结果融合引擎

Confidence-Based Weighted Fusion 策略：
1. 规则置信度 >= 0.9 → 直接采纳规则结果（规则优先）
2. 规则和 LLM 一致 → 取 max 置信度强化
3. 规则和 LLM 冲突 → 高置信度优先，低置信度时以 LLM 为准
"""

from typing import Dict, Any, Optional, List


class FusionEngine:
    """规则与 LLM 结果融合引擎"""

    def __init__(self, rule_weight: float = 0.4, llm_weight: float = 0.6):
        """
        Args:
            rule_weight: 规则结果的权重（在融合评分中）
            llm_weight: LLM 结果的权重
        """
        self.rule_weight = rule_weight
        self.llm_weight = llm_weight

    def fuse(self,
             reply_id: str,
             rule_results: List[Dict[str, Any]],
             llm_result: Optional[Dict[str, Any]]) -> Dict[str, Any]:
        """融合规则和 LLM 的检测结果

        Args:
            reply_id: 回复 ID
            rule_results: 所有触发的规则结果列表
            llm_result: LLM 检测结果

        Returns:
            融合后的最终检测结果
        """
        # 合并规则结果
        rule_hallucination = None
        rule_confidence = 0.0
        rule_evidences = []

        for r in rule_results:
            if r.get("is_hallucination"):
                rule_hallucination = True
                rule_confidence = max(rule_confidence, r.get("confidence", 0.0))
                rule_evidences.append(r.get("evidence", ""))

        # 规则优先：高置信度规则直接采纳
        if rule_hallucination and rule_confidence >= 0.90:
            return self._build_result(
                reply_id=reply_id,
                is_hallucination=True,
                hallucination_type=self._infer_type(rule_results, llm_result),
                confidence=rule_confidence,
                evidence=" | ".join(rule_evidences),
                severity=self._infer_severity(rule_results, llm_result),
                rule_result={
                    "triggered": True,
                    "rules": [r.get("rule_name", "") for r in rule_results],
                    "confidence": rule_confidence,
                },
                llm_result=llm_result,
                final_source="rule_dominant",
            )

        # 无规则触发，完全依赖 LLM
        if not rule_results:
            if llm_result and llm_result.get("is_hallucination"):
                return self._build_result(
                    reply_id=reply_id,
                    is_hallucination=True,
                    hallucination_type=llm_result.get("hallucination_type"),
                    confidence=llm_result.get("confidence", 0.0) * 0.9,
                    evidence=llm_result.get("evidence", "仅 LLM 检测结果"),
                    severity=llm_result.get("severity"),
                    rule_result={"triggered": False, "rules": [], "confidence": 0.0},
                    llm_result=llm_result,
                    final_source="llm_only",
                )
            return self._build_result(
                reply_id=reply_id,
                is_hallucination=False,
                hallucination_type=None,
                confidence=0.5,
                evidence="规则和LLM均未检测到幻觉",
                severity=None,
                rule_result={"triggered": False, "rules": [], "confidence": 0.0},
                llm_result=llm_result,
                final_source="no_detection",
            )

        # 两者都有结果，检查一致性
        llm_hallucination = llm_result.get("is_hallucination", False) if llm_result else False
        llm_confidence = llm_result.get("confidence", 0.0) if llm_result else 0.0

        if rule_hallucination == llm_hallucination:
            # 一致
            return self._build_result(
                reply_id=reply_id,
                is_hallucination=rule_hallucination,
                hallucination_type=self._infer_type(rule_results, llm_result),
                confidence=max(rule_confidence, llm_confidence),
                evidence=self._merge_evidence(rule_evidences, llm_result),
                severity=self._infer_severity(rule_results, llm_result),
                rule_result={
                    "triggered": True,
                    "rules": [r.get("rule_name", "") for r in rule_results],
                    "confidence": rule_confidence,
                },
                llm_result=llm_result,
                final_source="rule+llm_agreed",
            )
        else:
            # 冲突：取置信度更高的那个
            if rule_confidence >= llm_confidence:
                source = "rule_priority"
                return self._build_result(
                    reply_id=reply_id,
                    is_hallucination=rule_hallucination,
                    hallucination_type=self._infer_type(rule_results, llm_result),
                    confidence=rule_confidence,
                    evidence=f"[规则优先] {' | '.join(rule_evidences)}",
                    severity=self._infer_severity(rule_results, llm_result),
                    rule_result={
                        "triggered": True,
                        "rules": [r.get("rule_name", "") for r in rule_results],
                        "confidence": rule_confidence,
                    },
                    llm_result=llm_result,
                    final_source=source,
                    conflict=True,
                )
            else:
                return self._build_result(
                    reply_id=reply_id,
                    is_hallucination=llm_hallucination,
                    hallucination_type=llm_result.get("hallucination_type"),
                    confidence=llm_confidence * 0.8,
                    evidence=f"[LLM优先] {llm_result.get('evidence', '')}",
                    severity=llm_result.get("severity"),
                    rule_result={
                        "triggered": True,
                        "rules": [r.get("rule_name", "") for r in rule_results],
                        "confidence": rule_confidence,
                    },
                    llm_result=llm_result,
                    final_source="llm_priority",
                    conflict=True,
                )

    def _build_result(self, reply_id: str, **kwargs) -> Dict[str, Any]:
        """构建标准化的检测结果"""
        result = {
            "id": reply_id,
            "is_hallucination": kwargs.get("is_hallucination", False),
            "hallucination_type": kwargs.get("hallucination_type"),
            "confidence": kwargs.get("confidence", 0.0),
            "evidence": kwargs.get("evidence", ""),
            "severity": kwargs.get("severity"),
            "rule_result": kwargs.get("rule_result"),
            "llm_result": kwargs.get("llm_result"),
            "final_source": kwargs.get("final_source", ""),
        }
        if kwargs.get("conflict"):
            result["conflict"] = True
        return result

    def _infer_type(self, rule_results: List[Dict],
                    llm_result: Optional[Dict]) -> Optional[str]:
        """推断幻觉类型"""
        # 优先用 LLM 的类型
        if llm_result and llm_result.get("hallucination_type"):
            return llm_result.get("hallucination_type")

        # 否则从规则结果推断
        type_map = {
            "KB-Empty": "能力越界",
            "Numeric-Conflict": "参数编造",
            "Keyword-Negation": "信息编造",
            "Keyword-Negation-Safety": "安全误导",
        }
        for r in rule_results:
            rule_name = r.get("rule_name", "")
            if rule_name in type_map:
                return type_map[rule_name]

        return None

    def _infer_severity(self, rule_results: List[Dict],
                        llm_result: Optional[Dict]) -> Optional[str]:
        """推断严重程度"""
        if llm_result and llm_result.get("severity"):
            return llm_result.get("severity")
        return None

    def _merge_evidence(self, rule_evidences: List[str],
                        llm_result: Optional[Dict]) -> str:
        """合并证据"""
        parts = list(rule_evidences)
        if llm_result and llm_result.get("evidence"):
            parts.append(f"LLM: {llm_result['evidence']}")
        return " | ".join(parts)
