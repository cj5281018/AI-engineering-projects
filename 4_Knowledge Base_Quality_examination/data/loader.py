"""数据加载器：读取知识库JSON和业务规则Markdown"""

import json
from pathlib import Path
from .models import KBArticle


def load_kb_articles(filepath: str) -> list[KBArticle]:
    """加载 kb_articles.json → List[KBArticle]"""
    path = Path(filepath)
    if not path.exists():
        raise FileNotFoundError(f"知识库文件不存在: {filepath}")
    with open(path, "r", encoding="utf-8") as f:
        raw = json.load(f)
    return [KBArticle.from_dict(item) for item in raw]


def load_business_context(filepath: str) -> str:
    """加载 business_context.md 返回原始文本"""
    path = Path(filepath)
    if not path.exists():
        raise FileNotFoundError(f"业务规则文件不存在: {filepath}")
    with open(path, "r", encoding="utf-8") as f:
        return f.read()
