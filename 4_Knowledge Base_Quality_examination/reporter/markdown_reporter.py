"""Markdown 报告生成器 → output/report_{mode}.md（面向业务方的可读报告）"""

import os
from datetime import datetime
from data.models import DetectionResult
from governance.advisor import GovernanceAdvisor
from governance.priorities import (
    get_priority_description,
    TYPE_SEVERITY_DESC,
)


def _score_bar_1_5(score: int, width: int = 5) -> str:
    """生成 1-5 分制的可视化进度条"""
    filled = score
    empty = width - score
    return "█" * filled + "░" * empty


class MarkdownReporter:
    """生成面向业务方可读的 Markdown 报告"""

    def __init__(self, output_dir: str, mode: str = "mock"):
        self.output_dir = output_dir
        self.mode = mode

    def generate(
        self,
        results: list[DetectionResult],
        advisor: GovernanceAdvisor,
    ) -> str:
        """生成 Markdown 报告，返回文件路径"""
        stats = advisor.get_summary_stats(results)

        lines = []
        lines.append("# 知识库质量检测报告\n")
        lines.append(
            f"> **生成时间**：{datetime.now().strftime('%Y-%m-%d %H:%M')}  \n"
        )
        lines.append(f"> **检测条目数**：{stats['total_articles']}  \n")
        lines.append(
            f"> **问题条目数**：{stats['articles_with_issues']}  \n"
        )
        lines.append(
            f"> **健康率**：{stats['health_rate']}%  \n"
        )

        # ─── 1. 检测摘要 ───
        lines.append("\n---\n")
        lines.append("## 1. 检测摘要\n")

        # 严重度分布
        lines.append("### 严重度分布\n")
        lines.append(
            "| 优先级 | 数量 | 说明 |\n"
            "|--------|------|------|\n"
        )
        for pri, label in [
            ("P0", "立即处理（24小时内）"),
            ("P1", "尽快处理（1周内）"),
            ("P2", "常规优化（下个迭代周期）"),
        ]:
            count = stats["severity_counts"].get(pri, 0)
            lines.append(f"| **{pri}** | {count} | {label} |\n")

        # 问题类型分布
        lines.append("\n### 问题类型分布\n")
        lines.append(
            "| 问题类型 | 数量 | 说明 |\n"
            "|---------|------|------|\n"
        )
        type_order = [
            "contradictory_business",
            "contradictory_internal",
            "outdated",
            "empty_answer",
            "duplicate",
            "unprofessional",
            "missing_coverage",
            "incomplete",
        ]
        type_labels = {
            "contradictory_business": "与业务规则矛盾",
            "contradictory_internal": "条目间矛盾",
            "outdated": "内容过时",
            "empty_answer": "空答案",
            "duplicate": "重复条目",
            "unprofessional": "表达不专业",
            "missing_coverage": "覆盖缺失",
            "incomplete": "回答不完整",
        }
        for t in type_order:
            count = stats["type_distribution"].get(t, 0)
            if count > 0 or t == "incomplete":
                label = type_labels.get(t, t)
                desc = TYPE_SEVERITY_DESC.get(t, "")
                lines.append(f"| {label} | {count} | {desc} |\n")

        # 各分类健康状况
        lines.append("\n### 各分类健康状况\n")
        lines.append(
            "| 分类 | 总条目 | 问题条目 | 健康率 |\n"
            "|------|-------|---------|-------|\n"
        )
        for cat, cstats in sorted(stats["by_category"].items()):
            lines.append(
                f"| {cat} | {cstats['total']} | "
                f"{cstats['issues']} | {cstats['health_rate']}% |\n"
            )

        # 质量维度评分（对齐 DAMA-DMBOK 标准：1-5分制，等权重）
        quality_scores = stats.get("quality_scores", {})
        if quality_scores:
            lines.append("\n### 质量维度评分\n")
            lines.append(
                "> 评分方法：DAMA-DMBOK 1-5分制（5=优秀，1=不合格），"
                "各维度等权重，CQS 为简单平均。\n"
            )
            composite = quality_scores.get("composite_score", 0)
            assessment = quality_scores.get("assessment", {})
            grade = assessment.get("grade", "N/A")
            label = assessment.get("label", "")
            lines.append(
                f"**CQS（综合质量得分）：{composite}/5.0 | "
                f"等级：{grade} - {label}**\n\n"
            )
            lines.append(
                f"{assessment.get('advice', '')}\n\n"
            )

            lines.append(
                "| 维度 | 评分 | 等级 | 参考标准 | 影响范围 |\n"
                "|------|------|------|---------|---------|\n"
            )
            dims = quality_scores.get("dimensions", {})
            for dim_id in ["accuracy", "completeness", "consistency",
                           "timeliness", "uniqueness", "validity"]:
                dim = dims.get(dim_id)
                if dim:
                    bar = _score_bar_1_5(dim["score"])
                    lines.append(
                        f"| **{dim['name']}** | {bar} {dim['score']}/5 | "
                        f"{dim['score_label']} | "
                        f"{dim['standard']} | "
                        f"{dim['affected_count']}条 ({dim['affected_ratio']}%) |\n"
                    )

            lines.append(
                "\n**健康率说明**：健康率 = 完全无问题条目数 / 总条目数。"
                "CQS（综合质量得分）按 DAMA-DMBOK 1-5分制、等权重计算，"
                "反映知识库综合质量水平。\n"
            )

        # ─── 2. 按优先级排列问题条目 ───
        # 按优先级分组
        priority_groups: dict[str, list[DetectionResult]] = {
            "P0": [],
            "P1": [],
            "P2": [],
        }
        for result in results:
            pri = (
                result.governance.priority
                if result.governance
                else "P2"
            )
            priority_groups[pri].append(result)

        lines.append("\n---\n")
        lines.append("## 2. 问题详情\n")

        for pri in ["P0", "P1", "P2"]:
            group = priority_groups[pri]
            if not group:
                continue

            lines.append(f"\n### {get_priority_description(pri)}\n")

            for result in sorted(
                group, key=lambda r: r.article.id
            ):
                article = result.article
                # 问题类型标签
                type_tags = " ".join(
                    f"`{type_labels.get(i.type, i.type)}`"
                    for i in result.issues
                )
                lines.append(
                    f"\n### {article.id} - 「{article.question}」\n"
                )
                lines.append(f"- **分类**：{article.category}  \n")
                lines.append(f"- **问题类型**：{type_tags}  \n")

                if result.governance:
                    lines.append(
                        f"- **建议操作**：**{result.governance.action}**"
                        f"  \n"
                    )

                # 具体问题
                lines.append("\n**发现的问题：**\n")
                for i, issue in enumerate(result.issues, 1):
                    lines.append(
                        f"{i}. **[{issue.type}]** "
                        f"{issue.detail}  \n"
                    )
                    if issue.expected:
                        lines.append(
                            f"   - 应改为：{issue.expected}  \n"
                        )
                    if issue.suggestion:
                        # 截取建议到合理长度
                        suggestion = (
                            issue.suggestion[:200]
                            if len(issue.suggestion) > 200
                            else issue.suggestion
                        )
                        lines.append(
                            f"   - 建议：{suggestion}  \n"
                        )
                    if issue.related_articles:
                        lines.append(
                            f"   - 关联条目："
                            f"{', '.join(issue.related_articles)}  \n"
                        )

        # ─── 3. 治理建议汇总 ───
        lines.append("\n---\n")
        lines.append("## 3. 治理建议汇总\n")

        action_counts = stats.get("action_counts", {})
        lines.append(
            "| 操作类型 | 说明 | 数量 |\n"
            "|---------|------|------|\n"
        )
        action_descriptions = {
            "update": "修改现有条目",
            "merge": "合并重复条目",
            "delete": "删除废弃条目",
            "create": "新增缺失条目",
            "improve": "优化表达",
        }
        for action, desc in action_descriptions.items():
            count = action_counts.get(action, 0)
            if count > 0:
                lines.append(
                    f"| **{action}** | {desc} | {count} |\n"
                )

        # 详细列表
        lines.append("\n**涉及条目：**\n")
        for result in sorted(
            results, key=lambda r: r.article.id
        ):
            if result.governance:
                action = result.governance.action
                lines.append(
                    f"- [{action}] {result.article.id} - "
                    f"「{result.article.question}」  \n"
                )

        # 检测方法说明
        lines.append("\n---\n")
        lines.append(
            "## 4. 检测方法说明\n"
        )
        lines.append(
            "本报告采用 **双轨检测架构**，参考以下权威标准：\n\n"
            "### 参考框架\n\n"
            "| 框架 | 用途 |\n"
            "|------|------|\n"
            "| **DAMA-DMBOK**（数据管理知识体系） | 8 项数据质量维度定义（准确性/完整性/一致性/时效性/唯一性/规范性） |\n"
            "| **ISO 8000-61**（数据质量过程模型） | 质量改进 PDCA 循环，纠正措施（Corrective Action）框架 |\n"
            "| **KCS**（知识中心服务方法论） | Content Health Indicators，文章质量标准检查清单 |\n"
            "| **TDQM**（全面数据质量管理） | Define→Measure→Analyze→Improve 持续改进循环 |\n"
            "| **ICIS 2025**（RAG数据质量挑战研究） | RAG 系统中数据质量问题的 4 阶段传播机制 |\n\n"
            "### 双轨检测\n\n"
            "1. **规则引擎（确定性检测）**：基于业务规则文件，"
            "通过正则匹配和结构化对比检测：\n"
            "   - 内容过时（数值对比 / 布尔对比 / 枚举对比）\n"
            "   - 空答案 / 过短答案\n"
            "   - 重复条目（精确+模糊匹配）\n"
            "   - 条目间矛盾（同类别断言对比）\n\n"
            "2. **LLM 语义检测**：使用大语言模型检测：\n"
            "   - 语义矛盾（条目间软矛盾）\n"
            "   - 表达专业度\n"
            "   - 改进建议生成\n\n"
            "### 质量评分方法\n\n"
            "**评分标准**：DAMA-DMBOK 1-5分制，等权重简单平均。\n\n"
            "| 分数 | 等级 | 含义 |\n"
            "|------|------|------|\n"
            "| 5 | 优秀 | 无条目受影响 |\n"
            "| 4 | 良好 | ≤10% 条目受影响 |\n"
            "| 3 | 一般 | 10%~25% 条目受影响 |\n"
            "| 2 | 待改善 | 25%~50% 条目受影响 |\n"
            "| 1 | 不合格 | >50% 条目受影响 |\n\n"
            "**CQS（综合质量得分）** = 6 项维度得分的简单平均（等权重各 1/6）。\n\n"
            "**健康率** = 完全无问题条目数 / 总条目数。"
            "健康率反映「零缺陷」比例，CQS 通过多维度评分更全面反映质量水平。\n"
        )

        # 写入文件
        os.makedirs(self.output_dir, exist_ok=True)
        filename = f"report_{self.mode}.md"
        filepath = os.path.join(self.output_dir, filename)
        with open(filepath, "w", encoding="utf-8") as f:
            f.writelines(lines)

        return filepath
