"""全局配置 — 从 config.yaml 加载"""

import os
import yaml

# 项目根目录
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CONFIG_PATH = os.path.join(PROJECT_ROOT, "config.yaml")


def _load_config() -> dict:
    """加载 config.yaml"""
    if not os.path.exists(CONFIG_PATH):
        raise FileNotFoundError(
            f"配置文件不存在: {CONFIG_PATH}\n"
            "请复制 config.yaml 到项目根目录后进行配置。"
        )
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


_config = _load_config()


def _resolve(path: str) -> str:
    """相对路径转绝对路径（相对于项目根目录）"""
    if os.path.isabs(path):
        return path
    return os.path.normpath(os.path.join(PROJECT_ROOT, path))


class Settings:
    """配置项常量"""

    # LLM 模式
    LLM_MODE: str = _config.get("llm_mode", "mock")

    # DeepSeek API
    _ds = _config.get("deepseek", {})
    DEEPSEEK_API_KEY: str = _ds.get("api_key", "")
    DEEPSEEK_MODEL: str = _ds.get("model", "deepseek-chat")
    DEEPSEEK_BASE_URL: str = _ds.get("base_url", "https://api.deepseek.com")

    # 数据文件路径
    _data = _config.get("data", {})
    KB_FILE: str = _resolve(
        _data.get("kb_file", "4_task_requirements/task6_kb_articles.json")
    )
    BUSINESS_CONTEXT_FILE: str = _resolve(
        _data.get(
            "business_context_file",
            "4_task_requirements/task6_business_context.md",
        )
    )

    # 输出目录
    OUTPUT_DIR: str = _resolve(
        _config.get("output_dir", "output")
    )

    # 检测阈值
    _th = _config.get("thresholds", {})
    INCOMPLETE_THRESHOLD: int = _th.get("incomplete_min_chars", 10)
    DUPLICATE_SIMILARITY_THRESHOLD: float = _th.get(
        "duplicate_similarity", 0.8
    )
