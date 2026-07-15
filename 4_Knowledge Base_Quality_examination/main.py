#!/usr/bin/env python3
"""知识库质量检测工具 — CLI 入口

用法:
    # Mock 模式（无需 API Key）
    python main.py --mode mock

    # 真实 API 模式
    python main.py --mode real --api-key sk-xxx

    # 指定输出目录
    python main.py --mode mock --output-dir ./my_output
"""

import argparse
import sys
import os

# 确保项目根目录在 Python 路径中
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from config.settings import Settings
from data.loader import load_kb_articles, load_business_context
from rules.engine import RuleEngine
from llm.mock_detector import MockLLMDetector
from governance.advisor import GovernanceAdvisor
from reporter.json_reporter import JSONReporter
from reporter.markdown_reporter import MarkdownReporter


def parse_args():
    parser = argparse.ArgumentParser(
        description="知识库质量检测工具 — 自动扫描 FAQ 条目，检测质量问题并生成治理报告",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  python main.py --mode mock
  python main.py --mode real --api-key sk-xxx
  python main.py --mode mock --output-dir ./my_output
        """,
    )
    parser.add_argument(
        "--mode",
        choices=["mock", "real"],
        default=Settings.LLM_MODE,
        help="LLM 检测模式: mock（模拟）或 real（真实 API）",
    )
    parser.add_argument(
        "--api-key",
        default=Settings.DEEPSEEK_API_KEY,
        help="DeepSeek API Key（real 模式必需）",
    )
    parser.add_argument(
        "--output-dir",
        default=Settings.OUTPUT_DIR,
        help="报告输出目录",
    )
    parser.add_argument(
        "--kb-file",
        default=Settings.KB_FILE,
        help="知识库 JSON 文件路径",
    )
    parser.add_argument(
        "--business-context",
        default=Settings.BUSINESS_CONTEXT_FILE,
        help="业务规则 Markdown 文件路径",
    )
    return parser.parse_args()


def main():
    args = parse_args()

    print("=" * 60)
    print("  知识库质量检测工具 v1.0")
    print("=" * 60)

    # 1. 加载数据
    print()
    print("[1/5] 加载知识库数据...")
    articles = load_kb_articles(args.kb_file)
    print("      已加载 %d 条 FAQ" % len(articles))

    print("[2/5] 加载业务规则...")
    business_text = load_business_context(args.business_context)
    print("      已加载业务规则文件")

    # 2. 规则引擎检测
    print()
    print("[3/5] 规则引擎检测中...")
    engine = RuleEngine(business_text)
    rule_issues = engine.run(articles)
    print("      规则引擎发现 %d 个问题" % len(rule_issues))

    # 3. LLM 检测
    print()
    print("[4/5] LLM 语义检测中（模式: %s）..." % args.mode)
    if args.mode == "real":
        if not args.api_key:
            print("      [错误] real 模式需要提供 --api-key 参数")
            sys.exit(1)
        from llm.real_detector import DeepSeekDetector
        detector = DeepSeekDetector()
    else:
        detector = MockLLMDetector()

    llm_issues = []
    for article in articles:
        issues = detector.analyze_article(article, business_text)
        llm_issues.extend(issues)
    print("      LLM 检测发现 %d 个问题" % len(llm_issues))

    # 4. 治理建议
    print()
    print("[5/5] 生成治理建议...")
    advisor = GovernanceAdvisor(articles)
    results = advisor.build_results(rule_issues, llm_issues)
    stats = advisor.get_summary_stats(results)
    print("      共 %d 条目有问题（健康率 %s%%）" % (
        stats['articles_with_issues'], stats['health_rate']))

    # 5. 生成报告
    print()
    print("生成报告中...")
    os.makedirs(args.output_dir, exist_ok=True)

    json_reporter = JSONReporter(args.output_dir, args.mode)
    json_path = json_reporter.generate(results, advisor)
    print("  JSON报告: %s" % json_path)

    md_reporter = MarkdownReporter(args.output_dir, args.mode)
    md_path = md_reporter.generate(results, advisor)
    print("  Markdown报告: %s" % md_path)

    # 6. 打印摘要
    print()
    print("=" * 60)
    print("  检测完成！摘要")
    print("=" * 60)
    print("  总条目:     %d" % stats['total_articles'])
    print("  问题条目:   %d" % stats['articles_with_issues'])
    print("  健康率:     %s%%" % stats['health_rate'])
    print("  总问题数:   %d" % stats['total_issues'])
    print("  P0 (立即):  %d" % stats['severity_counts'].get('P0', 0))
    print("  P1 (尽快):  %d" % stats['severity_counts'].get('P1', 0))
    print("  P2 (常规):  %d" % stats['severity_counts'].get('P2', 0))

    print()
    print("报告文件:")
    print("  JSON:   %s" % json_path)
    print("  MD:     %s" % md_path)
    print()


if __name__ == "__main__":
    main()
