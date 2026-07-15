"""数据加载模块"""

import json
import os
from typing import List, Dict, Any

from src.config import config


def load_replies(filepath: str = None) -> List[Dict[str, Any]]:
    """加载回复数据"""
    if filepath is None:
        filepath = config.get_replies_path()
    with open(filepath, 'r', encoding='utf-8') as f:
        data = json.load(f)
    return data


def load_ground_truth(filepath: str = None) -> Dict[str, Dict[str, Any]]:
    """加载人工标注结果，以 id 为 key 的字典"""
    if filepath is None:
        filepath = config.get_ground_truth_path()
    with open(filepath, 'r', encoding='utf-8') as f:
        data = json.load(f)
    return {item["id"]: item for item in data}


def get_input_paths() -> tuple:
    """获取输入文件路径"""
    return config.get_replies_path(), config.get_ground_truth_path()


def get_output_dir() -> str:
    """获取输出目录"""
    return config.get_output_dir()
