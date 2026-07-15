#!/usr/bin/env python3
"""客服回复幻觉检测工具 — 主入口

用法：
    # Mock 模式（默认，无需 API Key）
    python src/main.py

    # DeepSeek 模式
    python src/main.py --provider deepseek

    # 指定输出格式
    python src/main.py --output json --output csv

    # 指定输出目录
    python src/main.py --output-dir ./my_output
"""

import sys
import os
import json
import argparse

# 确保可以从项目根目录导入
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.config import config
from src.utils.data_loader import load_replies, load_ground_truth, get_input_paths, get_output_dir
from src.rules.kb_empty_rule import KBEmptyRule
from src.rules.numeric_conflict_rule import NumericConflictRule
from src.rules.keyword_negation_rule import KeywordNegationRule
from src.llm.llm_client import LLMProvider, create_llm_client
from src.llm.llm_judge import detect_with_llm
from src.llm.mock_llm import MOCK_RESPONSES
from src.fusion.fusion_engine import FusionEngine
from src.evaluation.metrics import calculate_metrics
from src.evaluation.misanalysis import analyze_misjudgments
from src.utils.output_writer import (
    write_json, write_csv, write_metrics, print_console_results,
)
from src.utils.report_generator import generate_report


def parse_args():
    """解析命令行参数"""
    parser = argparse.ArgumentParser(
        description="客服回复幻觉检测工具",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例：
    python src/main.py                        # Mock 模式（默认）
    python src/main.py --provider deepseek    # DeepSeek 模式
    python src/main.py --output json --output csv  # 同时输出 JSON 和 CSV
        """,
    )
    parser.add_argument(
        "--provider", type=str, default=config.LLM_PROVIDER,
        choices=["mock", "deepseek"],
        help=f"LLM 提供商 (默认: {config.LLM_PROVIDER})",
    )
    parser.add_argument(
        "--output", type=str, action="append", default=[],
        choices=["json", "csv"],
        help="输出格式（可多次指定，默认只打印控制台）",
    )
    parser.add_argument(
        "--output-dir", type=str, default=None,
        help=f"输出目录（默认: {config.OUTPUT_DIR}）",
    )
    parser.add_argument(
        "--input", type=str, default=None,
        help=f"输入文件路径（默认: {config.REPLIES_FILE}）",
    )
    return parser.parse_args()


def run_rules(reply):
    """运行所有规则检测"""
    rules = [
        KBEmptyRule(),
        NumericConflictRule(),
        KeywordNegationRule(),
    ]
    results = []
    for rule in rules:
        result = rule.detect(reply)
        if result is not None:
            results.append(result)
    return results


def main():
    """主入口"""
    args = parse_args()

    print("=" * 65)
    print("  客服回复幻觉检测工具")
    print(f"  LLM 提供商: {args.provider}")
    print("=" * 65)

    # 1. 加载数据
    replies_path, gt_path = get_input_paths()
    if args.input:
        replies_path = args.input

    replies = load_replies(replies_path)
    ground_truth = load_ground_truth(gt_path)
    print(f"\n📦 加载数据: {len(replies)} 条回复, {len(ground_truth)} 条标注")

    # 2. 创建 LLM 客户端
    llm_client = None

    if args.provider == "deepseek":
        api_key = config.get_deepseek_api_key()
        if not api_key:
            print("⚠️  未设置 DEEPSEEK_API_KEY 环境变量")
            print("   切换到 Mock 模式...")
            args.provider = "mock"
        else:
            try:
                llm_client = create_llm_client(
                    LLMProvider.DEEPSEEK,
                    api_key=api_key,
                    model=config.DEEPSEEK_MODEL,
                    base_url=config.DEEPSEEK_BASE_URL,
                )
                print("🤖 DeepSeek 客户端已创建")
            except Exception as e:
                print(f"⚠️  DeepSeek 客户端创建失败: {e}")
                print("   切换到 Mock 模式...")
                args.provider = "mock"

    if args.provider == "mock":
        llm_client = create_llm_client(LLMProvider.MOCK, mock_responses=MOCK_RESPONSES)
        print("🧪 Mock 模式 (使用预设模拟结果)")

    # 3. 运行检测
    fusion_engine = FusionEngine(
        rule_weight=config.FUSION_RULE_WEIGHT,
        llm_weight=config.FUSION_LLM_WEIGHT,
    )
    results = []

    print(f"\n🔍 正在对 {len(replies)} 条回复进行检测...\n")

    for i, reply in enumerate(replies, 1):
        reply_id = reply.get("id", "unknown")
        rule_results = run_rules(reply)

        llm_result = None
        if llm_client:
            llm_result = detect_with_llm(reply, llm_client)

        final_result = fusion_engine.fuse(reply_id, rule_results, llm_result)
        results.append(final_result)

        is_hall = final_result.get("is_hallucination", False)
        icon = "❌" if is_hall else "✅"
        h_type = final_result.get("hallucination_type") or "非幻觉"
        confidence = final_result.get("confidence", 0)
        print(f"  [{i:>2}/{len(replies)}] {icon} {reply_id}: {h_type} (conf={confidence:.2f})")

    # 4. 评估 vs ground truth
    print("\n📊 正在与 ground_truth 对比评估...")
    metrics = calculate_metrics(results, ground_truth)

    # 5. 准备输出目录
    suffix = f"_{args.provider}"
    output_dir = args.output_dir or config.get_output_dir()
    os.makedirs(output_dir, exist_ok=True)

    # 6. 误判分析
    print("🔎 正在分析误判原因...")
    misanalysis = analyze_misjudgments(results, ground_truth, metrics)

    # 7. 生成报告
    print("📝 正在生成检测报告...")
    report_path = generate_report(results, metrics, misanalysis, args.provider, output_dir)
    print(f"💾 检测报告已保存: {report_path}")

    # 8. 保存逐条结果（带后缀区分运行模式）

    result_path = os.path.join(output_dir, f"detection_result{suffix}.json")
    write_json(results, result_path)
    print(f"\n💾 检测结果已保存: {result_path}")

    metrics_path = os.path.join(output_dir, f"evaluation_metrics{suffix}.json")
    metrics_export = {k: v for k, v in metrics.items() if k not in ("details",)}
    metrics_export["misanalysis"] = misanalysis
    with open(metrics_path, 'w', encoding='utf-8') as f:
        json.dump(metrics_export, f, ensure_ascii=False, indent=2)
    print(f"💾 评估指标已保存: {metrics_path}")

    if "csv" in args.output:
        csv_path = os.path.join(output_dir, f"detection_result{suffix}.csv")
        write_csv(results, csv_path)
        print(f"💾 CSV 已保存: {csv_path}")

    # 冲突记录
    conflicts = [r for r in results if r.get("conflict")]
    if conflicts:
        conflict_path = os.path.join(output_dir, f"conflict_log{suffix}.json")
        with open(conflict_path, 'w', encoding='utf-8') as f:
            json.dump(conflicts, f, ensure_ascii=False, indent=2)
        print(f"💾 冲突记录已保存: {conflict_path} ({len(conflicts)} 条)")
    else:
        print("✅ 规则与 LLM 结果无冲突")

    # 9. 控制台输出
    print("\n" + "=" * 65)
    print_console_results(results, metrics)

    # 10. 误判分析摘要
    mis_summary = misanalysis.get("summary", {})
    print(f"\n  📋 误判分析摘要")
    print(f"  总误判: {mis_summary.get('total_misjudgments', 0)} 条 "
          f"(漏检: {mis_summary.get('false_negatives_count', 0)}, "
          f"误报: {mis_summary.get('false_positives_count', 0)})")

    if misanalysis.get("recommendations"):
        print(f"\n  💡 改进建议:")
        for rec in misanalysis["recommendations"]:
            print(f"    • {rec}")

    print("\n" + "=" * 65)
    print("  检测完成!")
    print("=" * 65 + "\n")


if __name__ == "__main__":
    main()
