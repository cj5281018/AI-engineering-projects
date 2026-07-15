"""解析 business_context.md → 结构化业务规则"""

import re
from typing import Optional
from data.models import BusinessRule, RuleItem


def parse_business_context(markdown_text: str) -> list[BusinessRule]:
    """将 Markdown 格式的业务规则解析为结构化 BusinessRule 列表"""
    rules: list[BusinessRule] = []
    current_topic: Optional[str] = None
    current_items: list[str] = []

    for line in markdown_text.split("\n"):
        # 匹配 ## 标题作为主题
        heading_match = re.match(r"^##\s+(.+)$", line.strip())
        if heading_match:
            # 保存上一个主题
            if current_topic and current_items:
                rules.append(_build_rule(current_topic, current_items))
            current_topic = heading_match.group(1).strip()
            current_items = []
        elif line.strip().startswith("- ") and current_topic:
            current_items.append(line.strip()[2:])

    # 保存最后一个主题
    if current_topic and current_items:
        rules.append(_build_rule(current_topic, current_items))

    return rules


def _build_rule(topic: str, items: list[str]) -> BusinessRule:
    """将主题名和条目列表构建为 BusinessRule"""
    rule_items = []
    for i, item in enumerate(items):
        field = f"{_topic_key(topic)}_{i}"
        key, value, rule_type = _extract_structured(item)
        rule_items.append(RuleItem(
            field=field,
            description=item,
            key=key,
            value=value,
            rule_type=rule_type,
        ))
    return BusinessRule(topic=topic, rules=rule_items)


def _topic_key(topic: str) -> str:
    """将中文主题转为英文键名"""
    mapping = {
        "退货政策": "return",
        "发货与物流": "shipping",
        "物流": "shipping",
        "支付": "payment",
        "发票": "invoice",
        "会员等级": "membership",
        "会员": "membership",
        "优惠券": "coupon",
        "优惠": "coupon",
        "客服渠道": "service",
        "客服": "service",
    }
    return mapping.get(topic, topic)


def _extract_structured(text: str) -> tuple[str, object, str]:
    """从规则文本中提取结构化键值对

    返回 (key, value, rule_type)
    rule_type: numeric / boolean / enum / text
    """
    # 数值类: "7 天无理由退货" → ("return_days", 7, "numeric")
    m = re.search(r"(\d+)\s*天", text)
    if m:
        return ("days", int(m.group(1)), "numeric")

    m = re.search(r"(\d+)\s*小时", text)
    if m:
        return ("hours", int(m.group(1)), "numeric")

    m = re.search(r"满(\d+)减(\d+)", text)
    if m:
        return ("满减门槛", int(m.group(1)), "numeric")

    m = re.search(r"(\d+)\s*折", text)
    if m:
        return ("discount", int(m.group(1)), "numeric")

    m = re.search(r"累计消费满(\d+)元", text)
    if m:
        return ("threshold", int(m.group(1)), "numeric")

    # 布尔类
    if re.search(r"(支持|可以).*(货到付款|纸质发票|叠加)", text):
        return (re.search(r"(货到付款|纸质发票|叠加)", text).group(1), True, "boolean")
    if re.search(r"(不支持|不可以|不).*(货到付款|纸质发票|叠加)", text):
        return (re.search(r"(货到付款|纸质发票|叠加)", text).group(1), False, "boolean")

    # 枚举/文本类：收集全部匹配，而非只取第一个
    carriers = ["顺丰", "中通", "韵达", "圆通", "申通", "EMS"]
    matched_carriers = [c for c in carriers if c in text]
    if matched_carriers:
        return ("carrier", matched_carriers, "enum_list")

    payment_keywords = ["微信", "支付宝", "银行卡", "花呗", "信用卡"]
    matched_payments = [pk for pk in payment_keywords if pk in text]
    if matched_payments:
        return ("payment", matched_payments, "enum_list")

    # 买家/商家承担
    if "买家承担" in text:
        return ("bearer", "buyer", "enum")
    if "商家承担" in text:
        return ("bearer", "seller", "enum")

    return ("description", text, "text")


def format_rules_for_prompt(rules: list[BusinessRule]) -> str:
    """将业务规则格式化为 LLM prompt 可读的文本"""
    lines = []
    for rule in rules:
        lines.append(f"## {rule.topic}")
        for item in rule.rules:
            lines.append(f"- {item.description}")
        lines.append("")
    return "\n".join(lines)
