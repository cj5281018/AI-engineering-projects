"""
配置加载模块 — 从 config.yaml 读取评估配置

优先级: 环境变量 > config.yaml > 硬编码默认值
"""

import os
from typing import Any


# 默认配置 (与 config.yaml 一致)
_DEFAULT_CONFIG = {
    "mode": "mock",
    "llm": {
        "type": "openai",
        "api_key": "",
        "base_url": "",
        "model": "",
    },
    "data": {
        "auto_replies": "data/auto_replies.json",
        "human_ref": "data/human_ref.json",
    },
    "output": {
        "results": "output/eval_results.json",
        "report": "output/eval_report.md",
    },
}

_config = None  # 单例缓存


def _load_yaml(path: str = "config.yaml") -> dict:
    """加载 YAML 配置文件"""
    if not os.path.exists(path):
        return {}
    try:
        import yaml
        with open(path, "r", encoding="utf-8") as f:
            return yaml.safe_load(f) or {}
    except ImportError:
        print("[警告] pyyaml 未安装，跳过 config.yaml。安装: pip install pyyaml")
        return {}
    except Exception as e:
        print(f"[警告] 读取 config.yaml 失败: {e}，将使用默认配置")
        return {}


def load_config() -> dict:
    """加载并合并配置 (优先级: 环境变量 > config.yaml > 默认值)"""
    global _config
    if _config is not None:
        return _config

    # 1. 从默认配置开始
    cfg = _deep_copy(_DEFAULT_CONFIG)

    # 2. 合并 config.yaml
    yaml_cfg = _load_yaml()
    _deep_merge(cfg, yaml_cfg)

    # 3. 环境变量覆盖 (仅覆盖 LLM 相关的敏感字段)
    env_key = os.environ.get("LLM_API_KEY", "")
    if env_key:
        cfg["llm"]["api_key"] = env_key

    _config = cfg
    return cfg


def get(key: str, default: Any = None) -> Any:
    """点号路径取值，如 get('llm.type')"""
    cfg = load_config()
    parts = key.split(".")
    val = cfg
    for p in parts:
        if isinstance(val, dict):
            val = val.get(p)
        else:
            return default
    return val if val is not None else default


def _deep_merge(base: dict, overlay: dict):
    """递归合并 overlay 到 base"""
    for key, val in overlay.items():
        if key in base and isinstance(base[key], dict) and isinstance(val, dict):
            _deep_merge(base[key], val)
        elif val is not None:
            base[key] = val


def _deep_copy(d: dict) -> dict:
    """简易深拷贝"""
    import copy
    return copy.deepcopy(d)
