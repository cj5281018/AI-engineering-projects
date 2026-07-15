"""LLM API 统一客户端抽象

支持 DeepSeek（OpenAI 兼容）、OpenAI、Mock 三种模式。
"""

import os
import json
from abc import ABC, abstractmethod
from typing import Dict, Any, Optional
from enum import Enum

try:
    from openai import OpenAI
except ImportError:
    OpenAI = None


class LLMProvider(Enum):
    DEEPSEEK = "deepseek"
    MOCK = "mock"


class LLMClient(ABC):
    """LLM 客户端抽象基类"""

    @abstractmethod
    def chat(self, system_prompt: str, user_prompt: str,
             temperature: float = 0.0, max_tokens: int = 1000) -> str:
        """调用 LLM 并返回响应文本"""
        pass


class DeepSeekClient(LLMClient):
    """DeepSeek API 客户端（OpenAI 兼容）"""

    def __init__(self, api_key: Optional[str] = None,
                 model: str = "deepseek-chat",
                 base_url: str = "https://api.deepseek.com"):
        if OpenAI is None:
            raise ImportError(
                "openai 包未安装。请运行: pip install openai"
            )

        self.api_key = api_key or os.getenv("DEEPSEEK_API_KEY")
        if not self.api_key:
            raise ValueError(
                "DeepSeek API Key 未设置。请通过环境变量 DEEPSEEK_API_KEY 设置，"
                "或使用 Mock 模式 (--provider mock)"
            )

        self.client = OpenAI(api_key=self.api_key, base_url=base_url)
        self.model = model

    def chat(self, system_prompt: str, user_prompt: str,
             temperature: float = 0.0, max_tokens: int = 1000) -> str:
        response = self.client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            temperature=temperature,
            max_tokens=max_tokens,
            response_format={"type": "json_object"},
        )
        return response.choices[0].message.content


class MockClient(LLMClient):
    """Mock 客户端 — 返回预设的模拟结果"""

    def __init__(self, mock_responses: Dict[str, str] = None):
        self.mock_responses = mock_responses or {}

    def chat(self, system_prompt: str, user_prompt: str,
             temperature: float = 0.0, max_tokens: int = 1000) -> str:
        # 从 user_prompt 中提取 reply id（支持中文格式）
        import re
        id_match = re.search(r'(?:回复ID|id)[：:]\s*(h\d+)', user_prompt, re.IGNORECASE)
        reply_id = id_match.group(1) if id_match else "unknown"

        if reply_id in self.mock_responses:
            return json.dumps(self.mock_responses[reply_id], ensure_ascii=False)
        else:
            return json.dumps({
                "is_hallucination": False,
                "hallucination_type": None,
                "confidence": 0.5,
                "evidence": "Mock 模式：无预设结果，默认返回非幻觉",
                "severity": None,
                "rule_tippable": False,
            }, ensure_ascii=False)


def create_llm_client(provider: LLMProvider,
                      mock_responses: Optional[Dict[str, Dict]] = None,
                      **kwargs) -> LLMClient:
    """工厂方法：创建 LLM 客户端"""
    if provider == LLMProvider.DEEPSEEK:
        return DeepSeekClient(**kwargs)
    elif provider == LLMProvider.MOCK:
        return MockClient(mock_responses=mock_responses or {})
    else:
        raise ValueError(f"不支持的 LLM 提供商: {provider}")
