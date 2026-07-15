"""误判分析 — 分析漏检和误报的原因

对检测结果中与 ground_truth 不一致的 case 进行逐条分析，
归纳容易误判的场景和模式。
"""

from typing import Dict, Any, List


# 已知的难点 case 分析（基于对20条数据的人工预判）
KNOWN_DIFFICULT_CASES = {
    "h04": {
        "difficulty": "中",
        "reason": "部分正确部分错误。电子发票说对了但纸质发票是编造的。规则难以处理这种'半对半错'的情况，LLM 需要细致逐句对比。",
        "risk": "可能漏检（如果 LLM 只看到了正确的部分）或类型误判",
        "prevention": "Prompt 要求逐句对比，任何不一致即标记为幻觉",
    },
    "h07": {
        "difficulty": "中高",
        "reason": "能力越界+信息编造的混合。知识库说'需系统自动匹配后短信发送'，回复直接给地址。规则只能通过 KB-Empty（不适用，KB 非空）或关键词匹配（需要理解'不可口头告知'的语义）。",
        "risk": "规则完全无法检出，完全依赖 LLM 的语义理解",
        "prevention": "KB-Empty 规则不适用，完全依赖 LLM",
    },
    "h09": {
        "difficulty": "中",
        "reason": "知识库说'未标注NFC功能'——不等于'不支持NFC'。Keyword-Negation 规则可能误判为肯定（如果 '未标注NFC'↔'支持NFC' 匹配成功），但 LLM 应该能理解'未标注'和'不支持'的区别。",
        "risk": "规则可能误报，但 LLM 可纠正",
        "prevention": "规则层对此类设较低置信度，由 LLM 做语义判断",
    },
    "h15": {
        "difficulty": "中",
        "reason": "同 h09 类似。知识库说'未提及其他品牌关联关系'，回复说'XX旗下子品牌'。Keyword-Negation 规则可能检测到，LLM 需要做语义推理。",
        "risk": "规则可能漏检（匹配不到关键词对），LLM 需要判断",
        "prevention": "扩展 Keyword-Negation 的匹配模式",
    },
    "h20": {
        "difficulty": "高",
        "reason": "信息遗漏型幻觉的边界最模糊。回复'尺码标准不偏'本身不是错误陈述，但知识库有'30%反馈偏大半码'的关键信息。LLM 需要判断'遗漏信息是否属于重要信息'。",
        "risk": "最易漏检的 case，LLM 可能认为这不是幻觉",
        "prevention": "Prompt 明确将'遗漏知识库关键信息'定义为幻觉",
    },
}


def analyze_misjudgments(
    detection_results: List[Dict[str, Any]],
    ground_truth: Dict[str, Dict[str, Any]],
    metrics: Dict[str, Any],
) -> Dict[str, Any]:
    """分析误判 case 并归纳原因

    Args:
        detection_results: 检测结果列表
        ground_truth: 人工标注结果
        metrics: 评估指标（含漏检/误报列表）

    Returns:
        误判分析报告
    """
    false_negatives = metrics.get("false_negatives", [])
    false_positives = metrics.get("false_positives", [])
    type_recall = metrics.get("type_recall", {})

    analysis = {
        "summary": {
            "total_misjudgments": len(false_negatives) + len(false_positives),
            "false_negatives_count": len(false_negatives),
            "false_positives_count": len(false_positives),
        },
        "false_negatives": [],
        "false_positives": [],
        "type_analysis": [],
        "difficult_cases": [],
        "recommendations": [],
    }

    # 分析漏检
    for fn in false_negatives:
        fn_id = fn.get("id", "")
        case_analysis = {
            "id": fn_id,
            "ground_truth_type": fn.get("ground_truth_type"),
            "prediction_type": fn.get("prediction_type"),
            "source": fn.get("final_source"),
            "confidence": fn.get("confidence"),
            "known_difficulty": KNOWN_DIFFICULT_CASES.get(fn_id, {}),
        }
        analysis["false_negatives"].append(case_analysis)

    # 分析误报
    for fp_result in false_positives:
        fp_id = fp_result.get("id", "")
        case_analysis = {
            "id": fp_id,
            "prediction_type": fp_result.get("prediction_type"),
            "source": fp_result.get("final_source"),
            "confidence": fp_result.get("confidence"),
            "known_difficulty": KNOWN_DIFFICULT_CASES.get(fp_id, {}),
        }
        analysis["false_positives"].append(case_analysis)

    # 分类型漏检率分析
    for h_type, stats in type_recall.items():
        if stats["missed"] > 0:
            analysis["type_analysis"].append({
                "type": h_type,
                "total": stats["total"],
                "detected": stats["detected"],
                "missed": stats["missed"],
                "recall": stats["recall"],
                "risk_level": "高" if stats["recall"] < 0.8 else "中" if stats["recall"] < 0.95 else "低",
            })

    # 难点 case 汇总
    for case_id, info in KNOWN_DIFFICULT_CASES.items():
        analysis["difficult_cases"].append({
            "id": case_id,
            "difficulty": info["difficulty"],
            "reason": info["reason"],
            "risk": info["risk"],
        })

    # 总体建议
    recommendations = []
    if len(false_negatives) > 0:
        recommendations.append(
            f"存在 {len(false_negatives)} 个漏检，主要集中在信息遗漏和部分正确部分错误的 case，"
            f"建议增强 LLM Prompt 中对信息遗漏的判断要求"
        )
    if len(false_positives) > 0:
        recommendations.append(
            f"存在 {len(false_positives)} 个误报，建议检查规则层的阈值设置"
        )
    for ta in analysis["type_analysis"]:
        if ta["missed"] > 0:
            recommendations.append(
                f"{ta['type']}类型的检出率为 {ta['recall']:.1%}，"
                f"漏检了 {ta['missed']}/{ta['total']} 条，需特别关注"
            )
    analysis["recommendations"] = recommendations

    return analysis
