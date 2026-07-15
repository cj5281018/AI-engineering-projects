"""LLM 判断逻辑封装

调用 LLM 对回复进行幻觉检测，解析返回的 JSON 结果。
"""

import json
import re
from typing import Dict, Any, Optional

from .llm_client import LLMClient
from .prompts import (
    HALLUCINATION_DETECTION_SYSTEM_PROMPT,
    HALLUCINATION_DETECTION_USER_PROMPT,
)


def parse_llm_response(response_text: str) -> Optional[Dict[str, Any]]:
    """解析 LLM 返回的 JSON 响应"""
    # 尝试直接解析 JSON
    try:
        result = json.loads(response_text)
        return result
    except json.JSONDecodeError:
        pass

    # 尝试从 markdown 代码块中提取 JSON
    json_match = re.search(r'```(?:json)?\s*([\s\S]*?)```', response_text)
    if json_match:
        try:
            result = json.loads(json_match.group(1))
            return result
        except json.JSONDecodeError:
            pass

    return None


def detect_with_llm(reply: Dict[str, Any],
                    llm_client: LLMClient) -> Dict[str, Any]:
    """对单条回复进行 LLM 幻觉检测

    Args:
        reply: 包含 user_question, system_reply, knowledge_base 的字典
        llm_client: LLM 客户端实例

    Returns:
        检测结果字典，至少包含:
            - is_hallucination: bool
            - hallucination_type: str or None
            - confidence: float
            - evidence: str
            - severity: str or None
    """
    user_prompt = HALLUCINATION_DETECTION_USER_PROMPT.format(
        reply_id=reply.get("id", "unknown"),
        user_question=reply.get("user_question", ""),
        system_reply=reply.get("system_reply", ""),
        knowledge_base=reply.get("knowledge_base", ""),
    )

    try:
        response_text = llm_client.chat(
            system_prompt=HALLUCINATION_DETECTION_SYSTEM_PROMPT,
            user_prompt=user_prompt,
        )
    except Exception as e:
        return {
            "is_hallucination": False,
            "hallucination_type": None,
            "confidence": 0.0,
            "evidence": f"LLM 调用失败：{str(e)}",
            "severity": None,
            "error": str(e),
        }

    result = parse_llm_response(response_text)
    if result is None:
        return {
            "is_hallucination": False,
            "hallucination_type": None,
            "confidence": 0.0,
            "evidence": f"LLM 返回无法解析的响应：{response_text[:200]}",
            "severity": None,
            "raw_response": response_text,
        }

    return result
