"""文本处理工具函数"""

import re
from typing import List, Dict


def extract_numeric_claims(text: str) -> List[Dict]:
    """从文本中提取带单位的数值声明"""
    patterns = [
        (r'(\d+[\.\d]*)\s*天', '天数', 'days'),
        (r'(\d+[\.\d]*)\s*小时', '小时', 'hours'),
        (r'(\d+[\.\d]*)\s*个月', '月数', 'months'),
        (r'(\d+[\.\d]*)\s*年', '年数', 'years'),
        (r'蓝牙\s*(\d+[\.\d]*)', '蓝牙版本', 'bluetooth'),
        (r'满(\d+)\s*减(\d+)', '满减', 'discount'),
        (r'(\d+)\s*ms', '延迟ms', 'latency'),
        (r'(\d+)[-~](\d+)\s*天', '天数范围', 'days'),
        (r'(\d+)[-~](\d+)\s*小时', '小时范围', 'hours'),
        (r'(\d+)折', '折扣', 'discount_rate'),
        (r'(\d+)%', '百分比', 'percent'),
    ]
    results = []
    for pattern, claim_type, category in patterns:
        for match in re.finditer(pattern, text):
            results.append({
                'value': match.group(),
                'type': claim_type,
                'category': category,
                'position': match.span(),
            })
    return results


def compare_numeric_values(val1: str, val2: str) -> bool:
    """比较两个数值字符串是否冲突（不相等即为冲突）"""
    def extract_numbers(s: str) -> List[float]:
        return [float(x) for x in re.findall(r'\d+[\.\d]*', s)]

    nums1 = extract_numbers(val1)
    nums2 = extract_numbers(val2)
    return nums1 != nums2
