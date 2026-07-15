"""优先级排序逻辑"""

# 问题类型 → 优先级映射
TYPE_PRIORITY_MAP = {
    "contradictory_business": "P0",
    "empty_answer": "P0",
    "contradictory_internal": "P1",
    "outdated": "P1",
    "duplicate": "P1",
    "unprofessional": "P2",
    "missing_coverage": "P2",
    "incomplete": "P2",
}

# 优先级排序权重（数字越小越优先）
PRIORITY_ORDER = {"P0": 0, "P1": 1, "P2": 2}

# 问题类型 → 建议动作映射
TYPE_ACTION_MAP = {
    "contradictory_business": "update",
    "empty_answer": "create",
    "contradictory_internal": "update",
    "outdated": "update",
    "duplicate": "merge",
    "unprofessional": "improve",
    "missing_coverage": "create",
    "incomplete": "update",
}

# 问题类型 → 严重度中文描述
TYPE_SEVERITY_DESC = {
    "contradictory_business": "与业务规则直接矛盾，导致客服给出完全错误的回答",
    "empty_answer": "答为空，客服看到条目但无内容可用",
    "contradictory_internal": "条目间说法不一致，造成用户困惑",
    "outdated": "信息过时，与当前业务规则不符",
    "duplicate": "重复条目，浪费维护成本",
    "unprofessional": "表达不专业，影响品牌形象",
    "missing_coverage": "业务规则中的内容在知识库中缺失",
    "incomplete": "回答不完整，缺少关键信息",
}


def calculate_priority(issue_types: list[str]) -> str:
    """根据问题类型列表计算综合优先级（取最高）"""
    priorities = [TYPE_PRIORITY_MAP.get(t, "P2") for t in issue_types]
    priorities.sort(key=lambda p: PRIORITY_ORDER.get(p, 99))
    return priorities[0] if priorities else "P2"


def get_action(issue_type: str) -> str:
    """根据问题类型返回建议动作"""
    return TYPE_ACTION_MAP.get(issue_type, "update")


def get_severity_description(issue_type: str) -> str:
    """返回问题类型的严重度描述"""
    return TYPE_SEVERITY_DESC.get(issue_type, "")


def get_priority_description(priority: str) -> str:
    """返回优先级描述"""
    descriptions = {
        "P0": "P0 — 立即处理（24小时内）：直接导致用户投诉或法律风险",
        "P1": "P1 — 尽快处理（1周内）：信息过时或内部矛盾，影响用户体验",
        "P2": "P2 — 常规优化（下个迭代周期）：表达优化或补充覆盖",
    }
    return descriptions.get(priority, "")


