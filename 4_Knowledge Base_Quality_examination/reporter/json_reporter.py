"""JSON 报告生成器 → output/report_{mode}.json"""

import json
import os
from datetime import datetime
from data.models import DetectionResult
from governance.advisor import GovernanceAdvisor


class JSONReporter:
    """生成结构化 JSON 报告"""

    def __init__(self, output_dir: str, llm_mode: str = "mock"):
        self.output_dir = output_dir
        self.llm_mode = llm_mode

    def generate(
        self,
        results: list[DetectionResult],
        advisor: GovernanceAdvisor,
    ) -> str:
        """生成 JSON 报告文件，返回文件路径"""
        stats = advisor.get_summary_stats(results)

        # 构建报告
        report = {
            "report_meta": {
                "generated_at": datetime.now().strftime(
                    "%Y-%m-%d %H:%M:%S"
                ),
                "total_articles": stats["total_articles"],
                "llm_mode": self.llm_mode,
                "reference_frameworks": [
                    "DAMA-DMBOK 8 Data Quality Dimensions",
                    "ISO 8000-61 Data Quality Process Model",
                    "KCS Content Health Indicators",
                    "TDQM Continuous Improvement Cycle",
                    "ICIS 2025 Data Quality Challenges in RAG",
                ],
            },
            "summary": {
                "total_issues": stats["total_issues"],
                "articles_with_issues": stats[
                    "articles_with_issues"
                ],
                "healthy_articles": stats["healthy_articles"],
                "health_rate": stats["health_rate"],
                "severity_counts": stats["severity_counts"],
                "type_distribution": stats["type_distribution"],
                "by_category": {
                    k: {
                        "total": v["total"],
                        "issues": v["issues"],
                        "health_rate": v["health_rate"],
                    }
                    for k, v in stats["by_category"].items()
                },
            },
            "quality_scores": stats.get("quality_scores", {}),
            "issues": self._build_issues(results),
            "governance_actions": self._build_actions(results),
            "priority_order": self._build_priorities(results),
            "category_overview": self._build_category_overview(
                stats["by_category"]
            ),
        }

        os.makedirs(self.output_dir, exist_ok=True)
        filename = f"report_{self.llm_mode}.json"
        filepath = os.path.join(self.output_dir, filename)
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(report, f, ensure_ascii=False, indent=2)

        return filepath

    def _build_issues(
        self, results: list[DetectionResult]
    ) -> list[dict]:
        """构建问题条目列表"""
        issues_list = []
        for result in sorted(
            results,
            key=lambda r: (
                r.governance.priority if r.governance else "P2",
                r.article.id,
            ),
        ):
            article = result.article
            entry = {
                "id": article.id,
                "question": article.question,
                "category": article.category,
                "issues_found": [
                    {
                        "type": i.type,
                        "detail": i.detail,
                        "severity": i.severity,
                        "source": i.source,
                        "expected": i.expected,
                        "suggestion": i.suggestion,
                    }
                    for i in result.issues
                ],
            }
            if result.governance:
                entry["governance_suggestion"] = {
                    "action": result.governance.action,
                    "priority": result.governance.priority,
                    "summary": result.governance.summary,
                }
            issues_list.append(entry)
        return issues_list

    def _build_actions(
        self, results: list[DetectionResult]
    ) -> dict[str, list]:
        """按操作类型汇总治理建议"""
        actions: dict[str, list] = {
            "update": [],
            "merge": [],
            "delete": [],
            "create": [],
            "improve": [],
        }
        for result in results:
            if not result.governance:
                continue
            action = result.governance.action
            if action not in actions:
                continue

            # 收集 related_articles（去重）
            related = sorted(
                set(
                    ra for issue in result.issues
                    if issue.related_articles
                    for ra in issue.related_articles
                )
            )

            if action == "merge" and related:
                actions[action].append(
                    f"{result.article.id} ↔ {', '.join(related)}"
                )
            elif action != "merge":
                actions[action].append(
                    f"{result.article.id} - {result.article.question}"
                )
        return {k: v for k, v in actions.items() if v}

    def _build_priorities(
        self, results: list[DetectionResult]
    ) -> list[dict]:
        """按优先级分组"""
        groups: dict[str, list[str]] = {
            "P0": [],
            "P1": [],
            "P2": [],
        }
        for result in results:
            if result.governance:
                pri = result.governance.priority
                groups[pri].append(
                    f"{result.article.id} - "
                    f"{result.article.question}"
                )
        priority_order = []
        for pri, desc in [
            ("P0", "立即处理（24小时内）：直接导致用户投诉或法律风险"),
            (
                "P1",
                "尽快处理（1周内）：信息过时或内部矛盾，"
                "影响用户体验",
            ),
            (
                "P2",
                "常规优化（下个迭代周期）：表达优化或补充覆盖",
            ),
        ]:
            if groups[pri]:
                priority_order.append({
                    "priority": pri,
                    "description": desc,
                    "items": groups[pri],
                })
        return priority_order

    def _build_category_overview(
        self, category_stats: dict
    ) -> list[dict]:
        """按分类构建概览"""
        overview = []
        for cat, stats in sorted(category_stats.items()):
            overview.append({
                "category": cat,
                "total": stats["total"],
                "issues": stats["issues"],
                "health_rate": stats["health_rate"],
            })
        return overview
