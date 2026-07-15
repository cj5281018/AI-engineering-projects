"""内容过时检测器：KB条目 vs 业务规则的结构化对比

将 KB 条目中的关键信息（数值、布尔值、枚举值）
与业务规则进行结构化对比，检测：
- outdated: 数值有级差（如 48h vs 24h）
- contradictory_business: 布尔相反（如"支持" vs "不支持"）
"""

import re
from data.models import KBArticle, BusinessRule, Issue


# KB category → business rule topic 映射
CATEGORY_TOPIC_MAP = {
    "退货政策": "退货政策",
    "物流": "发货与物流",
    "支付": "支付",
    "发票": "发票",
    "会员": "会员等级",
    "优惠": "优惠券",
    "客服": "客服渠道",
    "售后": None,
    "订单": None,
    "账号": None,
}

# 快递公司列表
CARRIERS = ["顺丰", "中通", "韵达", "圆通", "申通", "EMS"]


def check_outdated(
    article: KBArticle, rules: list[BusinessRule]
) -> list[Issue]:
    """检测单条KB条目是否过时或与业务规则矛盾

    返回 Issue 列表（可能包含多个维度的检测结果）
    """
    topic = CATEGORY_TOPIC_MAP.get(article.category)
    if not topic:
        return []  # 找不到对应主题则跳过

    # 找到匹配的业务规则
    matched_rule = None
    for rule in rules:
        if rule.topic == topic:
            matched_rule = rule
            break

    if not matched_rule:
        return []

    issues: list[Issue] = []

    # 对每条规则子项进行对比
    for rule_item in matched_rule.rules:
        if rule_item.rule_type == "numeric":
            check_numeric(article, rule_item, issues)
        elif rule_item.rule_type == "boolean":
            check_boolean(article, rule_item, issues)
        elif rule_item.rule_type in ("enum", "enum_list"):
            check_enum(article, rule_item, issues)

    return issues


def check_numeric(
    article: KBArticle, rule_item, issues: list[Issue]
):
    """检测数值类规则是否过时"""
    answer = article.answer
    expected_val = rule_item.value
    expected_text_in_answer = str(expected_val) in answer

    if rule_item.key == "days":
        # 检测天数: 如果答案中出现了期望值则正确
        # (如 "7天无理由退货" 同时提到 7天和30天都是正确的)
        if not expected_text_in_answer:
            values = _extract_numbers_before(answer, "天")
            other_vals = [v for v in values if v != expected_val]
            if other_vals:
                issues.append(Issue(
                    article_id=article.id,
                    type="outdated",
                    detail=(
                        f"条目声称「{other_vals[0]}天」，"
                        f"但当前业务规则为「{expected_val}天」"
                    ),
                    severity="medium",
                    source="rule_engine",
                    expected=f"{expected_val}天",
                    suggestion=f"将天数修改为{expected_val}天，以匹配当前业务规则",
                ))

    elif rule_item.key == "hours":
        # 检测小时数
        if not expected_text_in_answer:
            values = _extract_numbers_before(answer, "小时")
            other_vals = [v for v in values if v != expected_val]
            if other_vals:
                issues.append(Issue(
                    article_id=article.id,
                    type="outdated",
                    detail=(
                        f"条目声称「{other_vals[0]}小时内发货」，"
                        f"但当前业务规则为「{expected_val}小时内发货」"
                    ),
                    severity="medium",
                    source="rule_engine",
                    expected=f"{expected_val}小时内发货",
                    suggestion=f"将发货时间修改为{expected_val}小时",
                ))

    elif rule_item.key == "discount":
        # 检测折扣
        if not expected_text_in_answer:
            values = _extract_numbers_before(answer, "折")
            other_vals = [v for v in values if v != expected_val]
            if other_vals:
                issues.append(Issue(
                    article_id=article.id,
                    type="outdated",
                    detail=(
                        f"条目声称「{other_vals[0]}折」，"
                        f"但当前业务规则为「{expected_val}折」"
                    ),
                    severity="medium",
                    source="rule_engine",
                    expected=f"{expected_val}折",
                    suggestion=f"将折扣修改为{expected_val}折",
                ))

    elif rule_item.key == "threshold":
        # 检测会员门槛
        if not expected_text_in_answer:
            values = _extract_numbers_before(answer, "元")
            other_vals = [v for v in values if v != expected_val]
            if other_vals:
                issues.append(Issue(
                    article_id=article.id,
                    type="outdated",
                    detail=(
                        f"条目声称门槛为「{other_vals[0]}元」，"
                        f"但当前业务规则为「{expected_val}元」"
                    ),
                    severity="medium",
                    source="rule_engine",
                    expected=f"{expected_val}元",
                    suggestion=f"将门槛金额修改为{expected_val}元",
                ))

    # 通用满减检测交由规则的数值对比处理，不再单独硬编码
    # （_check_generic_满减已移除，因其使用硬编码值且对所有类别误触发）
    pass


def check_boolean(
    article: KBArticle, rule_item, issues: list[Issue]
):
    """检测布尔类规则是否矛盾（支持 vs 不支持）"""
    answer = article.answer
    keyword = rule_item.key  # "货到付款" / "纸质发票" / "叠加"
    expected = rule_item.value  # True=支持, False=不支持

    # KB 条目中的说法
    if re.search(rf"支持.*{keyword}", answer):
        kb_supports = True
    elif re.search(rf"可以.*{keyword}", answer):
        kb_supports = True
    elif re.search(rf"{keyword}.*可以", answer):
        kb_supports = True
    elif re.search(rf"{keyword}.*支持", answer):
        kb_supports = True
    elif re.search(rf"{keyword}.*能", answer):
        kb_supports = True
    elif re.search(rf"不支持.*{keyword}", answer):
        kb_supports = False
    elif re.search(rf"不可以.*{keyword}", answer):
        kb_supports = False
    else:
        return  # 未提及，跳过

    if kb_supports != expected:
        expected_text = "支持" if expected else "不支持"
        kb_text = "支持" if kb_supports else "不支持"
        issues.append(Issue(
            article_id=article.id,
            type="contradictory_business",
            detail=(
                f"条目声称「{kb_text}{keyword}」，"
                f"但当前业务规则明确「{expected_text}{keyword}」"
            ),
            severity="high",
            source="rule_engine",
            expected=f"{expected_text}{keyword}",
            suggestion=f"将内容修改为「{expected_text}{keyword}」，与当前业务规则保持一致",
        ))


def check_enum(
    article: KBArticle, rule_item, issues: list[Issue]
):
    """检测枚举类规则是否一致（如快递公司、支付方式）"""
    answer = article.answer
    expected_value = rule_item.value

    if rule_item.key == "carrier":
        # expected_value 可能是单个字符串或列表
        if isinstance(expected_value, list):
            expected_carriers = expected_value
        else:
            expected_carriers = [expected_value]

        mentioned = [c for c in CARRIERS if c in answer]
        for carrier in mentioned:
            if carrier not in expected_carriers:
                issues.append(Issue(
                    article_id=article.id,
                    type="outdated",
                    detail=(
                        f"条目声称使用「{carrier}」，"
                        f"但当前合作快递为「{'/'.join(expected_carriers)}」"
                    ),
                    severity="medium",
                    source="rule_engine",
                    expected="/".join(expected_carriers),
                    suggestion=f"将快递公司修改为当前合作快递（{'/'.join(expected_carriers)}）",
                ))

    elif rule_item.key == "payment":
        # 检测 KB 中的支付方式描述
        pass  # 支付方式列举可能部分重叠，不做严格检测


def _extract_numbers_before(text: str, keyword: str) -> list[int]:
    """提取关键词前面的数字，如 "48小时" → [48]"""
    pattern = rf"(\d+)\s*{re.escape(keyword)}"
    matches = re.findall(pattern, text)
    return [int(m) for m in matches]


