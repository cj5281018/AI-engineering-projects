"""集中配置管理

从 config.yaml 读取所有可调参数。
"""

import os
import yaml
from typing import Dict, Any, List, Tuple


def _load_yaml() -> Dict[str, Any]:
    """加载 config.yaml 文件"""
    yaml_path = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "config.yaml",
    )
    if not os.path.exists(yaml_path):
        raise FileNotFoundError(f"配置文件不存在: {yaml_path}")
    with open(yaml_path, 'r', encoding='utf-8') as f:
        return yaml.safe_load(f)


class Config:
    """检测工具配置 — 从 config.yaml 加载"""

    def __init__(self):
        self._data = _load_yaml()

    # ==================== 输入输出 ====================
    @property
    def INPUT_DIR(self) -> str:
        return self._data.get("io", {}).get("input_dir", "data")

    @property
    def OUTPUT_DIR(self) -> str:
        return self._data.get("io", {}).get("output_dir", "output")

    @property
    def REPLIES_FILE(self) -> str:
        return self._data.get("io", {}).get("replies_file", "replies.json")

    @property
    def GROUND_TRUTH_FILE(self) -> str:
        return self._data.get("io", {}).get("ground_truth_file", "ground_truth.json")

    # ==================== LLM 配置 ====================
    @property
    def LLM_PROVIDER(self) -> str:
        return self._data.get("llm", {}).get("provider", "mock")

    @property
    def DEEPSEEK_MODEL(self) -> str:
        return self._data.get("llm", {}).get("deepseek", {}).get("model", "deepseek-chat")

    @property
    def DEEPSEEK_BASE_URL(self) -> str:
        return self._data.get("llm", {}).get("deepseek", {}).get("base_url", "https://api.deepseek.com")

    @property
    def DEEPSEEK_API_KEY(self) -> str:
        """优先取 config.yaml 中的值，否则读环境变量"""
        key = self._data.get("llm", {}).get("deepseek", {}).get("api_key", "")
        return key or os.getenv("DEEPSEEK_API_KEY", "")

    @property
    def LLM_TEMPERATURE(self) -> float:
        return self._data.get("llm", {}).get("temperature", 0.0)

    @property
    def LLM_MAX_TOKENS(self) -> int:
        return self._data.get("llm", {}).get("max_tokens", 1000)

    # ==================== 规则引擎配置 ====================
    @property
    def KB_EMPTY_CONFIDENCE(self) -> float:
        return self._data.get("rules", {}).get("kb_empty", {}).get("confidence", 0.92)

    @property
    def KB_EMPTY_TRIGGER_THRESHOLD(self) -> float:
        return self._data.get("rules", {}).get("kb_empty", {}).get("trigger_threshold", 0.90)

    @property
    def KB_EMPTY_PATTERNS(self) -> List[str]:
        return self._data.get("rules", {}).get("kb_empty", {}).get("patterns", [])

    @property
    def NUMERIC_CONFLICT_BASE_CONFIDENCE(self) -> float:
        return self._data.get("rules", {}).get("numeric_conflict", {}).get("base_confidence", 0.75)

    @property
    def NUMERIC_CONFLICT_BOOST_PER_CONFLICT(self) -> float:
        return self._data.get("rules", {}).get("numeric_conflict", {}).get("boost_per_conflict", 0.05)

    @property
    def NUMERIC_CONFLICT_MAX_CONFIDENCE(self) -> float:
        return self._data.get("rules", {}).get("numeric_conflict", {}).get("max_confidence", 0.90)

    @property
    def NUMERIC_EXTRACT_PATTERNS(self) -> List[Tuple]:
        """YAML 中存为 list，转为内部使用的 tuple 格式"""
        raw = self._data.get("rules", {}).get("numeric_conflict", {}).get("extract_patterns", [])
        return [tuple(item) for item in raw]

    @property
    def KEYWORD_NEGATION_CONFIDENCE(self) -> float:
        return self._data.get("rules", {}).get("keyword_negation", {}).get("confidence", 0.70)

    @property
    def KEYWORD_SAFETY_CONFIDENCE(self) -> float:
        return self._data.get("rules", {}).get("keyword_negation", {}).get("safety_confidence", 0.75)

    @property
    def NEGATION_KEYWORDS(self) -> List[str]:
        return self._data.get("rules", {}).get("keyword_negation", {}).get("negation_keywords", [])

    # ==================== 融合引擎配置 ====================
    @property
    def FUSION_RULE_WEIGHT(self) -> float:
        return self._data.get("fusion", {}).get("rule_weight", 0.4)

    @property
    def FUSION_LLM_WEIGHT(self) -> float:
        return self._data.get("fusion", {}).get("llm_weight", 0.6)

    @property
    def FUSION_RULE_DOMINANT_THRESHOLD(self) -> float:
        return self._data.get("fusion", {}).get("rule_dominant_threshold", 0.90)

    @property
    def FUSION_CONFLICT_LLM_PENALTY(self) -> float:
        return self._data.get("fusion", {}).get("conflict_llm_penalty", 0.8)

    # ==================== 映射 ====================
    @property
    def SEVERITY_MAP(self) -> Dict[str, str]:
        return self._data.get("severity_map", {})

    @property
    def TYPE_MAPPING(self) -> Dict[str, str]:
        return self._data.get("type_mapping", {})

    # ==================== 路径工具方法 ====================
    def get_project_root(self) -> str:
        return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

    def get_input_path(self, filename: str = None) -> str:
        if filename is None:
            filename = self.REPLIES_FILE
        return os.path.join(self.get_project_root(), self.INPUT_DIR, filename)

    def get_output_dir(self) -> str:
        path = os.path.join(self.get_project_root(), self.OUTPUT_DIR)
        os.makedirs(path, exist_ok=True)
        return path

    def get_replies_path(self) -> str:
        return self.get_input_path(self.REPLIES_FILE)

    def get_ground_truth_path(self) -> str:
        return self.get_input_path(self.GROUND_TRUTH_FILE)

    def get_deepseek_api_key(self) -> str:
        return self.DEEPSEEK_API_KEY


# 全局单例
config = Config()
