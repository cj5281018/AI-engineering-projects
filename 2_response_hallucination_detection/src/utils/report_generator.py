"""生成可读性检测报告（Markdown 格式）"""

import os
from datetime import datetime
from typing import Dict, Any, List


def generate_report(
    results: List[Dict[str, Any]],
    metrics: Dict[str, Any],
    misanalysis: Dict[str, Any],
    provider: str,
    output_dir: str,
) -> str:
    """生成一份完整的 Markdown 检测报告

    Args:
        results: 逐条检测结果
        metrics: 评估指标
        misanalysis: 误判分析
        provider: LLM 提供商 (mock/deepseek)
        output_dir: 输出目录

    Returns:
        报告文件路径
    """
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    suffix = f"_{provider}"

    lines = []
    _w = lambda text="": lines.append(text)

    # ===== 标题 =====
    _w(f"# 客服回复幻觉检测报告")
    _w()
    _w(f"- **检测时间**：{now}")
    _w(f"- **LLM 提供商**：{provider}")
    _w(f"- **检测总数**：{metrics.get('total_samples', 0)} 条")
    _w(f"- **真实幻觉数**：{metrics.get('true_hallucinations', 0)} 条")
    _w(f"- **真实非幻觉数**：{metrics.get('true_non_hallucinations', 0)} 条")
    _w()

    # ===== 1. 核心指标 =====
    _w("## 一、核心评估指标")
    _w()
    _w("| 指标 | 值 |")
    _w("|------|-----|")
    _w(f"| **准确率 (Accuracy)** | {metrics.get('accuracy', 0):.2%} |")
    _w(f"| **精确率 (Precision)** | {metrics.get('precision', 0):.2%} |")
    _w(f"| **召回率 (Recall)** | {metrics.get('recall', 0):.2%} |")
    _w(f"| **F1 分数** | {metrics.get('f1_score', 0):.2%} |")
    _w(f"| **特异度 (Specificity)** | {metrics.get('specificity', 0):.2%} |")
    _w()

    # ===== 2. 混淆矩阵 =====
    cm = metrics.get("confusion_matrix", {})
    _w("## 二、混淆矩阵")
    _w()
    _w("| \\ | 实际幻觉 | 实际非幻觉 |")
    _w("|---|---------|-----------|")
    _w(f"| **检测为幻觉** | TP = {cm.get('tp', 0)} | FP = {cm.get('fp', 0)} |")
    _w(f"| **检测为非幻觉** | FN = {cm.get('fn', 0)} | TN = {cm.get('tn', 0)} |")
    _w()

    # ===== 3. 分类型检出率 =====
    type_recall = metrics.get("type_recall", {})
    _w("## 三、分类型检出率")
    _w()
    _w("| 幻觉类型 | 总数 | 检出 | 漏检 | 召回率 |")
    _w("|---------|------|------|------|--------|")
    for t, stats in sorted(type_recall.items()):
        _w(f"| {t} | {stats['total']} | {stats['detected']} | {stats['missed']} | {stats['recall']:.1%} |")
    _w()

    # ===== 4. 各来源对比 =====
    source_comp = metrics.get("source_comparison", {})
    _w("## 四、各检测来源对比")
    _w()
    _w("| 来源 | 数量 | 精确率 | 召回率 | F1 |")
    _w("|------|------|--------|--------|-----|")
    for src, s in source_comp.items():
        _w(f"| {src} | {s['count']} | {s['precision']:.2%} | {s['recall']:.2%} | {s['f1']:.2%} |")
    _w()
    _w("- **rule_only**：规则置信度高，直接采纳规则结果")
    _w("- **llm_only**：规则未覆盖，完全依赖 LLM 判断")
    _w("- **hybrid**：规则与 LLM 一致或融合后综合判断")
    _w()

    # ===== 5. 逐条检测明细 =====
    _w("## 五、逐条检测明细")
    _w()
    _w("| ID | 结果 | 类型 | 严重度 | 置信度 | 决策来源 |")
    _w("|----|------|------|--------|--------|---------|")
    for r in results:
        is_hall = r.get("is_hallucination", False)
        result_str = "❌ 幻觉" if is_hall else "✅ 非幻觉"
        h_type = r.get("hallucination_type") or "-"
        sev = r.get("severity") or "-"
        conf = f"{r.get('confidence', 0):.2f}"
        source = r.get("final_source", "")
        _w(f"| {r.get('id', '')} | {result_str} | {h_type} | {sev} | {conf} | {source} |")
    _w()

    # 详细证据（可折叠）
    _w("### 检测证据详情")
    _w()
    for r in results:
        rid = r.get("id", "")
        is_hall = r.get("is_hallucination", False)
        icon = "❌" if is_hall else "✅"
        _w(f"<details>")
        _w(f"<summary>{icon} {rid}: {r.get('hallucination_type') or '非幻觉'} (conf={r.get('confidence', 0):.2f})</summary>")
        _w()
        _w(f"**证据**：{r.get('evidence', '无')}")
        _w()
        # LLM 分析细节
        llm = r.get("llm_result", {})
        if llm and llm.get("evidence") and "调用失败" not in llm.get("evidence", ""):
            _w(f"**LLM 分析**：{llm.get('evidence', '')}")
            _w()
            claims = llm.get("claims_analysis")
            if claims:
                _w("| 原子陈述 | 结论 | 说明 |")
                _w("|---------|------|------|")
                for c in claims:
                    verdict = c.get("verdict", "")
                    v_icon = {"supported": "✅", "contradicted": "❌", "unsupported": "❓", "incomplete": "⚠️"}.get(verdict, "➖")
                    _w(f"| {c.get('claim', '')} | {v_icon} {verdict} | {c.get('explanation', '')} |")
                _w()
        _w("</details>")
        _w()

    # ===== 6. 误判分析 =====
    _w("## 六、误判分析")
    _w()
    mis_summary = misanalysis.get("summary", {})
    _w(f"- **总误判数**：{mis_summary.get('total_misjudgments', 0)} 条")
    _w(f"- **漏检 (FN)**：{mis_summary.get('false_negatives_count', 0)} 条")
    _w(f"- **误报 (FP)**：{mis_summary.get('false_positives_count', 0)} 条")
    _w()

    # 漏检详情
    fn_list = misanalysis.get("false_negatives", [])
    if fn_list:
        _w("### 漏检 Case 分析")
        _w()
        _w("| ID | 真实类型 | 决策来源 | 置信度 | 预期难度 | 原因分析 |")
        _w("|----|---------|---------|--------|---------|---------|")
        for fn_item in fn_list:
            known = fn_item.get("known_difficulty", {})
            _w(f"| {fn_item.get('id', '')} | {fn_item.get('ground_truth_type', '')} | "
               f"{fn_item.get('source', '')} | {fn_item.get('confidence', 0):.2f} | "
               f"{known.get('difficulty', '')} | {known.get('reason', '')} |")
        _w()

    # 误报详情
    fp_list = misanalysis.get("false_positives", [])
    if fp_list:
        _w("### 误报 Case 分析")
        _w()
        _w("| ID | 预测类型 | 决策来源 | 置信度 | 分析 |")
        _w("|----|---------|---------|--------|------|")
        for fp_item in fp_list:
            known = fp_item.get("known_difficulty", {})
            _w(f"| {fp_item.get('id', '')} | {fp_item.get('prediction_type', '')} | "
               f"{fp_item.get('source', '')} | {fp_item.get('confidence', 0):.2f} | "
               f"{known.get('reason', '')} |")
        _w()

    # 已知难点 Case
    difficult = misanalysis.get("difficult_cases", [])
    if difficult:
        _w("### 已知难点 Case")
        _w()
        _w("| ID | 难度 | 原因 | 风险 |")
        _w("|----|------|------|------|")
        for d in difficult:
            _w(f"| {d.get('id', '')} | {d.get('difficulty', '')} | {d.get('reason', '')} | {d.get('risk', '')} |")
        _w()

    # 改进建议
    recommendations = misanalysis.get("recommendations", [])
    if recommendations:
        _w("### 改进建议")
        _w()
        for i, rec in enumerate(recommendations, 1):
            _w(f"{i}. {rec}")
        _w()

    # ===== 7. 配置信息 =====
    _w("## 七、检测配置")
    _w()
    _w(f"- **LLM 提供商**：{provider}")
    _w(f"- **规则引擎**：KB-Empty / Numeric-Conflict / Keyword-Negation")
    _w(f"- **融合策略**：Confidence-Based Weighted Fusion")
    _w()

    # 写入文件
    report_path = os.path.join(output_dir, f"detection_report{suffix}.md")
    with open(report_path, 'w', encoding='utf-8') as f:
        f.write("\n".join(lines))

    return report_path
