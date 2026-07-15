"""检出率评估指标计算

标准分类指标 + RAGAS 风格的 Faithfulness Score 评估。
"""

from typing import Dict, Any, List, Optional, Tuple


def calculate_metrics(
    detection_results: List[Dict[str, Any]],
    ground_truth: Dict[str, Dict[str, Any]],
) -> Dict[str, Any]:
    """计算检出率评估指标

    标准分类指标：
        - 精确率 (Precision)
        - 召回率 (Recall)
        - F1 分数
        - 准确率 (Accuracy)
        - 特异度 (Specificity)

    附加分析：
        - 混淆矩阵（二元）
        - 分类型检出率
        - 各来源（Rule-only / LLM-only / Hybrid）对比
    """
    # 构建 ground_truth 查询映射
    gt_lookup = {}
    for item_id, item in ground_truth.items():
        gt_lookup[item_id] = item

    # 初始统计
    tp = 0  # 真正例：真实幻觉且检测为幻觉
    tn = 0  # 真负例：真实非幻觉且检测为非幻觉
    fp = 0  # 假正例：真实非幻觉但检测为幻觉
    fn = 0  # 假负例：真实幻觉但检测为非幻觉

    # 分类型统计
    type_tp = {}
    type_fn = {}
    type_total = {}

    # 各来源统计（映射 final_source 到三个顶层类别）
    source_mapping = {
        "rule_dominant": "rule_only",
        "rule+llm_agreed": "hybrid",
        "llm_only": "llm_only",
        "llm_priority": "hybrid",
        "rule_priority": "hybrid",
        "no_detection": "hybrid",
    }
    source_stats = {
        "rule_only": {"tp": 0, "tn": 0, "fp": 0, "fn": 0, "total": 0},
        "llm_only": {"tp": 0, "tn": 0, "fp": 0, "fn": 0, "total": 0},
        "hybrid": {"tp": 0, "tn": 0, "fp": 0, "fn": 0, "total": 0},
    }

    # 分类映射（人工标注 8 类 → 本体系 6 类）
    type_mapping = {
        "参数编造": "参数编造",
        "政策编造": "政策编造",
        "政策偏差": "政策编造",
        "优惠编造": "政策编造",
        "能力越界": "能力越界",
        "信息编造": "信息编造",
        "安全误导": "安全误导",
        "信息遗漏": "信息遗漏",
    }

    # 逐条评估
    detail_records = []

    for result in detection_results:
        reply_id = result.get("id", "")
        gt_item = gt_lookup.get(reply_id)

        if not gt_item:
            continue

        gt_is_hallucination = gt_item.get("is_hallucination", False)
        gt_type = gt_item.get("hallucination_type")

        pred_is_hallucination = result.get("is_hallucination", False)
        pred_type = result.get("hallucination_type")

        if pred_is_hallucination and gt_is_hallucination:
            tp += 1
        elif not pred_is_hallucination and not gt_is_hallucination:
            tn += 1
        elif pred_is_hallucination and not gt_is_hallucination:
            fp += 1
        elif not pred_is_hallucination and gt_is_hallucination:
            fn += 1

        # 分类型统计（仅统计真实幻觉的 case）
        if gt_is_hallucination and gt_type:
            mapped_type = type_mapping.get(gt_type, gt_type)
            type_total[mapped_type] = type_total.get(mapped_type, 0) + 1
            if pred_is_hallucination:
                type_tp[mapped_type] = type_tp.get(mapped_type, 0) + 1
            else:
                type_fn[mapped_type] = type_fn.get(mapped_type, 0) + 1

        # 按来源统计（映射到三个顶层类别）
        raw_source = result.get("final_source", "hybrid")
        source_cat = source_mapping.get(raw_source, "hybrid")
        if source_cat in source_stats:
            source_stats[source_cat]["total"] += 1
            if pred_is_hallucination and gt_is_hallucination:
                source_stats[source_cat]["tp"] += 1
            elif not pred_is_hallucination and not gt_is_hallucination:
                source_stats[source_cat]["tn"] += 1
            elif pred_is_hallucination and not gt_is_hallucination:
                source_stats[source_cat]["fp"] += 1
            elif not pred_is_hallucination and gt_is_hallucination:
                source_stats[source_cat]["fn"] += 1

        # 详细记录
        detail_records.append({
            "id": reply_id,
            "ground_truth": gt_is_hallucination,
            "ground_truth_type": gt_type,
            "prediction": pred_is_hallucination,
            "prediction_type": pred_type,
            "match": pred_is_hallucination == gt_is_hallucination,
            "type_match": pred_type == (type_mapping.get(gt_type) if gt_type else None),
            "final_source": raw_source,
            "confidence": result.get("confidence", 0.0),
        })

    # 计算指标
    total = tp + tn + fp + fn
    metrics = {
        "total_samples": total,
        "true_hallucinations": tp + fn,
        "true_non_hallucinations": tn + fp,
        "true_positive": tp,
        "true_negative": tn,
        "false_positive": fp,
        "false_negative": fn,
    }

    # 核心指标
    metrics["accuracy"] = round((tp + tn) / total, 4) if total > 0 else 0.0
    metrics["precision"] = round(tp / (tp + fp), 4) if (tp + fp) > 0 else 0.0
    metrics["recall"] = round(tp / (tp + fn), 4) if (tp + fn) > 0 else 0.0
    metrics["f1_score"] = round(
        2 * metrics["precision"] * metrics["recall"] / (metrics["precision"] + metrics["recall"]),
        4,
    ) if (metrics["precision"] + metrics["recall"]) > 0 else 0.0
    metrics["specificity"] = round(tn / (tn + fp), 4) if (tn + fp) > 0 else 0.0

    # 混淆矩阵
    metrics["confusion_matrix"] = {
        "tp": tp, "fn": fn,
        "fp": fp, "tn": tn,
    }

    # 分类型检出率
    type_recall = {}
    for t, total_count in type_total.items():
        detected = type_tp.get(t, 0)
        type_recall[t] = {
            "total": total_count,
            "detected": detected,
            "missed": type_fn.get(t, 0),
            "recall": round(detected / total_count, 4) if total_count > 0 else 0.0,
        }
    metrics["type_recall"] = type_recall

    # 各来源对比
    source_metrics = {}
    for src, stats in source_stats.items():
        if stats["total"] == 0:
            continue
        s_tp, s_tn, s_fp, s_fn = stats["tp"], stats["tn"], stats["fp"], stats["fn"]
        s_total = s_tp + s_tn + s_fp + s_fn
        s_precision = round(s_tp / (s_tp + s_fp), 4) if (s_tp + s_fp) > 0 else 0.0
        s_recall = round(s_tp / (s_tp + s_fn), 4) if (s_tp + s_fn) > 0 else 0.0
        s_f1 = round(
            2 * s_precision * s_recall / (s_precision + s_recall), 4
        ) if (s_precision + s_recall) > 0 else 0.0
        source_metrics[src] = {
            "count": s_total,
            "precision": s_precision,
            "recall": s_recall,
            "f1": s_f1,
        }
    metrics["source_comparison"] = source_metrics

    # 详细记录
    metrics["details"] = detail_records

    # 漏检和误报列表
    metrics["false_negatives"] = [
        r for r in detail_records if r["ground_truth"] and not r["prediction"]
    ]
    metrics["false_positives"] = [
        r for r in detail_records if not r["ground_truth"] and r["prediction"]
    ]

    return metrics
