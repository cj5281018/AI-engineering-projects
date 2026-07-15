"""结果输出模块 — 支持控制台、JSON、CSV 三种输出格式"""

import json
import csv
import os
from typing import List, Dict, Any, Optional
from datetime import datetime


def write_json(results: List[Dict[str, Any]], filepath: str):
    """写入 JSON 文件"""
    # 清理结果中的非序列化字段
    cleaned = []
    for r in results:
        item = {}
        for k, v in r.items():
            if k == "llm_result" and isinstance(v, dict) and "claims_analysis" in v:
                # 保留 claims_analysis，但过长的可以截断
                pass
            item[k] = v
        cleaned.append(r)

    with open(filepath, 'w', encoding='utf-8') as f:
        json.dump(cleaned, f, ensure_ascii=False, indent=2)
    return filepath


def write_csv(results: List[Dict[str, Any]], filepath: str):
    """写入 CSV 文件"""
    fieldnames = [
        "id", "is_hallucination", "hallucination_type", "severity",
        "confidence", "final_source", "evidence",
    ]
    with open(filepath, 'w', encoding='utf-8-sig', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for r in results:
            writer.writerow({
                "id": r.get("id", ""),
                "is_hallucination": r.get("is_hallucination", False),
                "hallucination_type": r.get("hallucination_type", ""),
                "severity": r.get("severity", ""),
                "confidence": r.get("confidence", 0.0),
                "final_source": r.get("final_source", ""),
                "evidence": r.get("evidence", ""),
            })
    return filepath


def write_metrics(metrics: Dict[str, Any], filepath: str):
    """写入评估指标到 JSON"""
    with open(filepath, 'w', encoding='utf-8') as f:
        json.dump(metrics, f, ensure_ascii=False, indent=2)
    return filepath


def print_console_results(results: List[Dict[str, Any]],
                          metrics: Optional[Dict[str, Any]] = None):
    """在控制台打印结果表格"""
    try:
        from rich.console import Console
        from rich.table import Table
        from rich.panel import Panel
        from rich import box
        console = Console()
        rich_available = True
    except ImportError:
        rich_available = False

    header = "=" * 70
    print(header)
    print(f"  客服回复幻觉检测工具 — 检测结果")
    print(f"  检测时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(header)

    if rich_available:
        _print_rich_results(results, metrics, console)
    else:
        _print_plain_results(results)

    if metrics:
        print("\n" + "=" * 70)
        print("  评估指标汇总")
        print("=" * 70)
        print(f"  准确率 (Accuracy):  {metrics.get('accuracy', 'N/A')}")
        print(f"  精确率 (Precision): {metrics.get('precision', 'N/A')}")
        print(f"  召回率 (Recall):    {metrics.get('recall', 'N/A')}")
        print(f"  F1 分数:            {metrics.get('f1_score', 'N/A')}")
        print(f"  特异度 (Specificity): {metrics.get('specificity', 'N/A')}")
        print(f"  TP={metrics.get('true_positive')}  FN={metrics.get('false_negative')}  "
              f"FP={metrics.get('false_positive')}  TN={metrics.get('true_negative')}")

        # 分类型检出率
        type_recall = metrics.get("type_recall", {})
        if type_recall:
            print("\n  分类型检出率：")
            for t, stats in sorted(type_recall.items()):
                bar = "█" * int(stats['recall'] * 30) if stats['total'] > 0 else ""
                print(f"    {t}: {stats['detected']}/{stats['total']} "
                      f"({stats['recall']:.1%}) {bar}")

        # 各来源对比
        source_comp = metrics.get("source_comparison", {})
        if source_comp:
            print("\n  各来源对比：")
            for src, s in source_comp.items():
                print(f"    {src}: P={s['precision']:.2f} R={s['recall']:.2f} F1={s['f1']:.2f}")

    print("\n" + "=" * 70)


def _print_rich_results(results, metrics, console):
    """rich 格式输出"""
    from rich.table import Table
    from rich.panel import Panel
    from rich import box
    table = Table(title="检测结果明细", box=box.ROUNDED)
    table.add_column("ID", style="cyan")
    table.add_column("结果", style="bold")
    table.add_column("类型", style="yellow")
    table.add_column("严重度")
    table.add_column("置信度")
    table.add_column("来源")

    for r in results:
        is_hall = r.get("is_hallucination", False)
        result_str = "✅ 非幻觉" if not is_hall else "❌ 幻觉"
        result_style = "green" if not is_hall else "red"

        h_type = r.get("hallucination_type") or "-"
        severity = r.get("severity") or "-"
        confidence = f"{r.get('confidence', 0):.2f}"
        source = r.get("final_source", "")

        table.add_row(
            r.get("id", ""),
            f"[{result_style}]{result_str}[/{result_style}]",
            h_type,
            severity,
            confidence,
            source,
        )

    console.print(table)

    if metrics:
        # 指标面板
        metric_text = (
            f"准确率: {metrics.get('accuracy', 'N/A'):.2%}  |  "
            f"精确率: {metrics.get('precision', 'N/A'):.2%}  |  "
            f"召回率: {metrics.get('recall', 'N/A'):.2%}  |  "
            f"F1: {metrics.get('f1_score', 'N/A'):.2%}  |  "
            f"特异度: {metrics.get('specificity', 'N/A'):.2%}\n"
            f"TP={metrics.get('true_positive')}  FN={metrics.get('false_negative')}  "
            f"FP={metrics.get('false_positive')}  TN={metrics.get('true_negative')}"
        )
        panel = Panel(metric_text, title="评估指标", border_style="blue")
        console.print(panel)

        # 分类型检出率
        type_recall = metrics.get("type_recall", {})
        if type_recall:
            type_table = Table(title="分类型检出率", box=box.SIMPLE, title_style="bold blue")
            type_table.add_column("类型")
            type_table.add_column("检出/总数", justify="center")
            type_table.add_column("召回率", justify="center")
            type_table.add_column("状态")

            for t, stats in sorted(type_recall.items()):
                status = "✅" if stats['recall'] >= 0.9 else "⚠️" if stats['recall'] >= 0.5 else "❌"
                type_table.add_row(
                    t,
                    f"{stats['detected']}/{stats['total']}",
                    f"{stats['recall']:.1%}",
                    status,
                )
            console.print(type_table)

        # 各来源对比
        source_comp = metrics.get("source_comparison", {})
        if source_comp:
            src_table = Table(title="各来源对比", box=box.SIMPLE)
            src_table.add_column("来源")
            src_table.add_column("精确率", justify="center")
            src_table.add_column("召回率", justify="center")
            src_table.add_column("F1", justify="center")

            for src, s in source_comp.items():
                src_table.add_row(
                    src,
                    f"{s['precision']:.2%}",
                    f"{s['recall']:.2%}",
                    f"{s['f1']:.2%}",
                )
            console.print(src_table)


def _print_plain_results(results):
    """纯文本格式输出（兼容无 rich 环境）"""
    print(f"\n{'ID':<6} {'结果':<12} {'类型':<14} {'严重度':<8} {'置信度':<8} {'来源':<16}")
    print("-" * 70)
    for r in results:
        is_hall = r.get("is_hallucination", False)
        result_str = "幻觉" if is_hall else "非幻觉"
        h_type = r.get("hallucination_type") or "-"
        severity = r.get("severity") or "-"
        confidence = f"{r.get('confidence', 0):.2f}"
        source = r.get("final_source", "")

        print(f"{r.get('id', ''):<6} {result_str:<12} {h_type:<14} {severity:<8} "
              f"{confidence:<8} {source:<16}")
