"""DeepSeek API 模式 LLM 检测器

使用 OpenAI 兼容 SDK 调用 DeepSeek API 进行语义检测。
需安装: pip install openai
"""

import json
import re
from typing import Optional
from openai import OpenAI

from data.models import KBArticle, Issue
from llm.base import LLMDetector
from llm.prompts import PromptTemplates
from rules.parser import format_rules_for_prompt
from config.settings import Settings


class DeepSeekDetector(LLMDetector):
    """调用 DeepSeek API 进行真实 LLM 检测"""

    def __init__(self):
        self.client = OpenAI(
            api_key=Settings.DEEPSEEK_API_KEY or "sk-placeholder",
            base_url=Settings.DEEPSEEK_BASE_URL,
        )
        self.model = Settings.DEEPSEEK_MODEL

    def analyze_article(
        self, article: KBArticle, rules_text: str = ""
    ) -> list[Issue]:
        """调用 DeepSeek 分析单条条目"""
        if not Settings.DEEPSEEK_API_KEY:
            return self._fallback_empty(article)

        system_prompt = PromptTemplates.SYSTEM_ANALYZE_SINGLE.format(
            rules=rules_text
        )
        user_prompt = PromptTemplates.USER_ANALYZE_SINGLE.format(
            question=article.question,
            answer=article.answer,
            category=article.category,
            created_at=article.created_at,
            updated_at=article.updated_at,
        )

        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                temperature=0.1,
                response_format={"type": "json_object"},
            )
            content = response.choices[0].message.content
            return self._parse_response(content, article.id)
        except Exception as e:
            return [
                Issue(
                    article_id=article.id,
                    type="incomplete",
                    detail=f"LLM 检测异常: {str(e)}",
                    severity="low",
                    source="llm",
                )
            ]

    def check_semantic_contradiction(
        self, article_a: KBArticle, article_b: KBArticle
    ) -> Optional[Issue]:
        """检测两条条目间是否存在语义矛盾"""
        if not Settings.DEEPSEEK_API_KEY:
            return None

        system_prompt = PromptTemplates.SYSTEM_CHECK_CONTRADICTION
        user_prompt = PromptTemplates.USER_CHECK_CONTRADICTION.format(
            question_a=article_a.question,
            answer_a=article_a.answer,
            category_a=article_a.category,
            question_b=article_b.question,
            answer_b=article_b.answer,
            category_b=article_b.category,
        )

        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                temperature=0.1,
                response_format={"type": "json_object"},
            )
            content = response.choices[0].message.content
            data = json.loads(content)
            if data.get("has_contradiction"):
                return Issue(
                    article_id=article_a.id,
                    type="contradictory_internal",
                    detail=data.get("contradiction_detail", ""),
                    severity="high",
                    source="llm",
                    suggestion=data.get("suggestion"),
                    related_articles=[article_b.id],
                )
        except Exception as e:
            print(f"  [Warning] LLM 矛盾检测异常: {e}")
            return None

    def suggest_improvement(
        self, article: KBArticle, issues: list[Issue]
    ) -> str:
        """基于检测结果生成改进建议"""
        if not issues:
            return "条目内容与业务规则一致，无需修改。"

        issue_descriptions = "\n".join(
            f"- [{i.type}] {i.detail}" for i in issues
        )
        prompt = (
            f"基于以下问题，为知识库条目生成具体的改进建议：\n\n"
            f"问题：{article.question}\n"
            f"当前答案：{article.answer}\n"
            f"发现的问题：\n{issue_descriptions}\n\n"
            f"请给出修改后的建议版本："
        )

        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {
                        "role": "system",
                        "content": "你是一个知识库内容优化专家，请给出具体、可操作的改进方案。",
                    },
                    {"role": "user", "content": prompt},
                ],
                temperature=0.3,
            )
            return response.choices[0].message.content
        except Exception:
            return issues[0].suggestion or "请人工审核并修改。"

    def _parse_response(
        self, content: str, article_id: str
    ) -> list[Issue]:
        """解析 LLM 返回的 JSON 响应"""
        try:
            # 尝试从代码块中提取 JSON
            json_match = re.search(
                r"```(?:json)?\s*([\s\S]*?)```", content
            )
            if json_match:
                content = json_match.group(1)

            data = json.loads(content.strip())
            raw_issues = data.get("issues", [])
            return [
                Issue(
                    article_id=article_id,
                    type=ri.get("type", "incomplete"),
                    detail=ri.get("detail", ""),
                    severity=ri.get("severity", "medium"),
                    source="llm",
                    suggestion=ri.get("suggestion"),
                )
                for ri in raw_issues
                if ri.get("type")
            ]
        except (json.JSONDecodeError, KeyError):
            return [
                Issue(
                    article_id=article_id,
                    type="incomplete",
                    detail=f"LLM 返回格式解析失败: {content[:100]}",
                    severity="low",
                    source="llm",
                )
            ]

    def _fallback_empty(self, article: KBArticle) -> list[Issue]:
        """API Key 未配置时返回空结果"""
        return [
            Issue(
                article_id=article.id,
                type="incomplete",
                detail="DeepSeek API Key 未配置，跳过 LLM 检测",
                severity="low",
                source="llm",
            )
        ]
