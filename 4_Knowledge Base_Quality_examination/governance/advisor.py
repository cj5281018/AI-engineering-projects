"""治理建议生成器

合并规则引擎和 LLM 的检测结果，去重、生成治理建议、定优先级。
支持多维质量评分体系（参考 DAMA-DMBOK 数据质量维度标准）。
"""

from collections import defaultdict
from data.models import KBArticle, Issue, GovernanceAction, DetectionResult
from governance.priorities import (
    calculate_priority,
    get_action,
    get_priority_description,
)

# ── 质量维度定义（参考 DAMA-DMBOK 8 项数据质量维度）──
# 等权重：每项维度权重相同（均为 1/6）
QUALITY_DIMENSIONS = [
    {
        "id": "accuracy",
        "name": "准确性",
        "issue_types": {"contradictory_business"},
        "description": "信息与当前业务规则的一致性程度",
        "standard": "DAMA-DMBOK Accuracy / ISO 8000-130",
    },
    {
        "id": "completeness",
        "name": "完整性",
        "issue_types": {"empty_answer", "incomplete", "missing_coverage"},
        "description": "答案覆盖用户所需信息的完整程度",
        "standard": "DAMA-DMBOK Completeness / KCS Content Checklist",
    },
    {
        "id": "consistency",
        "name": "一致性",
        "issue_types": {"contradictory_internal"},
        "description": "不同条目之间说法的一致性",
        "standard": "DAMA-DMBOK Consistency / ISO 8000-140",
    },
    {
        "id": "timeliness",
        "name": "时效性",
        "issue_types": {"outdated"},
        "description": "信息与当前业务规则的同步程度",
        "standard": "DAMA-DMBOK Timeliness / Atlan Freshness Scoring",
    },
    {
        "id": "uniqueness",
        "name": "唯一性",
        "issue_types": {"duplicate"},
        "description": "条目不重复、无冗余的程度",
        "standard": "DAMA-DMBOK Uniqueness / KCS Uniqueness Check",
    },
    {
        "id": "validity",
        "name": "规范性",
        "issue_types": {"unprofessional"},
        "description": "表达的专业程度和服务规范性",
        "standard": "DAMA-DMBOK Validity / KCS Content Standard",
    },
]

# 治理动作 → 权威参考框架映射
GOVERNANCE_FRAMEWORKS = {
    "update": "ISO 8000-61 纠正措施（Corrective Action）：在数据源头修复，消除根本原因",
    "merge": "DAMA-DMBOK 重复数据治理（Duplicate Management）：保留权威版本，去除冗余",
    "delete": "ISO 8000-61 废弃流程（Obsolescence Process）：标记并移除失效数据",
    "create": "KCS 内容创建标准（Content Standard Checklist）：确保新条目完整、清晰、唯一",
    "improve": "TDQM 持续改进（Continuous Improvement）：Define→Measure→Analyze→Improve 循环",
}


class GovernanceAdvisor:
    """治理建议生成器"""

    def __init__(self, articles: list[KBArticle]):
        self.articles = {a.id: a for a in articles}

    def build_results(
        self, rule_issues: list[Issue], llm_issues: list[Issue]
    ) -> list[DetectionResult]:
        """合并规则引擎和 LLM 的检测结果，生成治理建议"""
        # 按 article_id 分组
        grouped: dict[str, list[Issue]] = defaultdict(list)
        for issue in rule_issues:
            grouped[issue.article_id].append(issue)
        for issue in llm_issues:
            grouped[issue.article_id].append(issue)

        # 去重：同一条目同一类型只保留一条
        for article_id in grouped:
            grouped[article_id] = self._deduplicate(grouped[article_id])

        results: list[DetectionResult] = []
        for article_id, issues in grouped.items():
            article = self.articles.get(article_id)
            if not article:
                continue

            issue_types = list(set(i.type for i in issues))
            priority = calculate_priority(issue_types)
            actions_set = set(get_action(t) for t in issue_types)

            # 多动作时按优先级选择：merge > create > improve > update
            action_priority = ["merge", "create", "improve", "update", "delete"]
            main_action = "update"
            for ap in action_priority:
                if ap in actions_set:
                    main_action = ap
                    break

            # 生成治理建议
            suggestion_parts = []
            for issue in issues:
                if issue.suggestion:
                    suggestion_parts.append(issue.suggestion)
            summary = self._generate_summary(article, issue_types)

            # 附加权威参考框架说明
            framework_ref = GOVERNANCE_FRAMEWORKS.get(main_action, "")
            if framework_ref:
                suggestion_parts.append(f"[参考框架] {framework_ref}")

            governance = GovernanceAction(
                action=main_action,
                summary=summary,
                priority=priority,
                detail="\n".join(suggestion_parts) if suggestion_parts else "",
            )

            results.append(DetectionResult(
                article=article,
                issues=issues,
                governance=governance,
            ))

        return results

    # ── 质量维度评分（对齐 DAMA-DMBOK 标准）──

    def calculate_quality_scores(
        self, results: list[DetectionResult]
    ) -> dict:
        """计算各质量维度得分和综合质量得分（CQS）

        对齐 DAMA-DMBOK 数据质量维度评估方法：
        - 每项维度按 1-5 分制评分（1=差, 5=优）
        - 各维度等权重（简单平均计算 CQS）
        - 评分依据问题影响条目的占比映射到 1-5 分
        """
        total = len(self.articles)

        # 统计每条目影响了哪些维度
        article_dimensions: dict[str, set[str]] = defaultdict(set)
        for result in results:
            for issue in result.issues:
                for dim in QUALITY_DIMENSIONS:
                    if issue.type in dim["issue_types"]:
                        article_dimensions[result.article.id].add(dim["id"])

        # 计算每项维度得分（1-5 分制）
        dimension_scores = {}
        num_dims = len(QUALITY_DIMENSIONS)
        for dim in QUALITY_DIMENSIONS:
            affected = sum(
                1 for arts in article_dimensions.values()
                if dim["id"] in arts
            )
            ratio = affected / total if total > 0 else 0
            score_1_5 = self._ratio_to_1_5(ratio)
            dimension_scores[dim["id"]] = {
                "name": dim["name"],
                "score": score_1_5,
                "score_label": self._score_label(score_1_5),
                "affected_count": affected,
                "affected_ratio": round(ratio * 100, 1),
                "description": dim["description"],
                "standard": dim["standard"],
            }

        # CQS = 简单平均（等权重）
        composite_raw = sum(
            dim["score"] for dim in dimension_scores.values()
        ) / num_dims
        composite = round(composite_raw, 1)

        return {
            "composite_score": composite,
            "dimensions": dimension_scores,
            "assessment": self._grade_assessment(composite),
            "methodology": (
                "DAMA-DMBOK 1-5分制，等权重简单平均"
            ),
        }

    @staticmethod
    def _ratio_to_1_5(ratio: float) -> int:
        """将受影响比例映射到 1-5 分

        5 = 0% 受影响（完美）
        4 = 0%~10%
        3 = 10%~25%
        2 = 25%~50%
        1 = >50%（差）
        """
        if ratio == 0:
            return 5
        elif ratio <= 0.10:
            return 4
        elif ratio <= 0.25:
            return 3
        elif ratio <= 0.50:
            return 2
        else:
            return 1

    @staticmethod
    def _score_label(score: int) -> str:
        mapping = {5: "优秀", 4: "良好", 3: "一般", 2: "待改善", 1: "不合格"}
        return mapping.get(score, "未知")

    def _grade_assessment(self, cqs: float) -> dict:
        """根据 CQS（1-5 分）给出等级评估"""
        if cqs >= 4.5:
            return {
                "grade": "A",
                "label": "优秀",
                "advice": "知识库质量良好，建议维持定期审核机制",
            }
        elif cqs >= 3.5:
            return {
                "grade": "B",
                "label": "良好",
                "advice": "有小部分条目需要优化，建议优先处理 P0 问题",
            }
        elif cqs >= 2.5:
            return {
                "grade": "C",
                "label": "一般",
                "advice": "存在一定数量的问题条目，建议系统性整改",
            }
        elif cqs >= 1.5:
            return {
                "grade": "D",
                "label": "待改善",
                "advice": "较多条目存在问题，需立即启动治理计划",
            }
        else:
            return {
                "grade": "F",
                "label": "不合格",
                "advice": "知识库质量严重不达标，建议全面重建",
            }

    # ── 治理建议生成 ──

    def _deduplicate(self, issues: list[Issue]) -> list[Issue]:
        """去重：同一类型问题只保留一条（保留 source 更多的）"""
        seen: dict[str, Issue] = {}
        for issue in issues:
            key = f"{issue.article_id}_{issue.type}"
            if key not in seen:
                seen[key] = issue
            else:
                # 保留 detail 更详细的
                if len(issue.detail) > len(seen[key].detail):
                    seen[key] = issue
        return list(seen.values())

    def _generate_summary(
        self, article, issue_types: list[str]
    ) -> str:
        """生成治理建议摘要"""
        if "contradictory_business" in issue_types:
            return (
                f"「{article.question}」与当前业务规则直接矛盾，"
                f"建议以业务规则为准重写答案"
            )
        elif "empty_answer" in issue_types:
            return f"「{article.question}」回答为空，建议补充完整答案"
        elif "contradictory_internal" in issue_types:
            return (
                f"「{article.question}」与其他条目说法矛盾，"
                f"建议统一说法"
            )
        elif "outdated" in issue_types:
            return (
                f"「{article.question}」信息已过时，"
                f"建议更新为当前业务规则"
            )
        elif "duplicate" in issue_types:
            return (
                f"「{article.question}」存在重复条目，"
                f"建议合并"
            )
        elif "unprofessional" in issue_types:
            return (
                f"「{article.question}」表达不够专业，"
                f"建议优化措辞"
            )
        elif "missing_coverage" in issue_types:
            return (
                f"「{article.question}」覆盖不完整，"
                f"建议补充相关信息"
            )
        return f"「{article.question}」建议优化完善"

    # ── 汇总统计 ──

    def get_summary_stats(
        self, results: list[DetectionResult]
    ) -> dict:
        """生成汇总统计数据，含质量维度得分"""
        total = len(self.articles)
        articles_with_issues = len(results)
        healthy = total - articles_with_issues

        type_count: dict[str, int] = defaultdict(int)
        priority_count: dict[str, int] = defaultdict(int)
        category_issues: dict[str, set[str]] = defaultdict(set)
        action_counts: dict[str, int] = defaultdict(int)

        for result in results:
            for issue in result.issues:
                type_count[issue.type] += 1
                category_issues[result.article.category].add(result.article.id)

            if result.governance:
                priority_count[result.governance.priority] += 1
                action_counts[result.governance.action] += 1

        # 按分类统计
        category_stats = {}
        for cat, ids in category_issues.items():
            total_in_cat = sum(
                1 for a in self.articles.values()
                if a.category == cat
            )
            category_stats[cat] = {
                "total": total_in_cat,
                "issues": len(ids),
                "health_rate": round(
                    (total_in_cat - len(ids)) / total_in_cat * 100, 1
                ),
                "articles_with_issues": sorted(ids),
            }

        # 质量维度评分
        quality_scores = self.calculate_quality_scores(results)

        return {
            "total_articles": total,
            "articles_with_issues": articles_with_issues,
            "healthy_articles": healthy,
            "health_rate": round(
                healthy / total * 100, 1
            ) if total > 0 else 0,
            "total_issues": sum(type_count.values()),
            "severity_counts": dict(priority_count),
            "type_distribution": dict(type_count),
            "action_counts": dict(action_counts),
            "by_category": dict(category_stats),
            "quality_scores": quality_scores,  # 新增：多维质量评分
        }
