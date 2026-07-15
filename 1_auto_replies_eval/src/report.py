"""
评估报告生成器

从 eval_results.json 读取评分结果，生成 Markdown 格式的评估报告，
包含: 整体得分、各指标分布、最差 3 条 case 深度分析。
"""

import json
import os
import sys
from statistics import mean, stdev
from typing import Optional

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from config import get as cfg_get


def _add_mode_suffix(path: str, mode: str) -> str:
    """在文件名中插入 mode 后缀，如 eval_report.md → eval_report_mock.md"""
    base, ext = os.path.splitext(path)
    return f"{base}_{mode}{ext}"


def _get_mode(path: str) -> str:
    """从文件名推断 mode，推断不出则回退到 config.yaml 配置"""
    base = os.path.basename(path)
    name, _ = os.path.splitext(base)
    for m in ("mock", "real"):
        if name.endswith(f"_{m}"):
            return m
    # 文件路径没后缀 → 从配置文件读
    return cfg_get("mode", "mock")


def load_results(path: str = "output/eval_results.json") -> list[dict]:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def _dim_scores(results: list[dict], dim: str) -> list[float]:
    return [r[dim]["score"] for r in results]


def _mean(vals: list[float]) -> float:
    return round(mean(vals), 2)


def _stdev(vals: list[float]) -> float:
    return round(stdev(vals), 2) if len(vals) > 1 else 0.0


def _grade_label(score: float) -> str:
    if score >= 4.5:
        return "优秀"
    elif score >= 3.5:
        return "良好"
    elif score >= 2.5:
        return "一般"
    else:
        return "较差"


def _score_bar(score: float, width: int = 20) -> str:
    """生成 ASCII 进度条"""
    filled = round(score / 5.0 * width)
    bar = "#" * filled + "." * (width - filled)
    return f"[{bar}] {score}/5"


def _ensure_mode_suffix(path: str, mode: str) -> str:
    """如果 path 还没有 mode 后缀，补上"""
    if not path.endswith(f"_{mode}."):
        return _add_mode_suffix(path, mode)
    return path


def generate_report(
    results_path: str = "output/eval_results.json",
    output_path: str = "output/eval_report.md",
    human_ref_path: Optional[str] = None,
):
    print("[生成报告] 加载结果...")

    # 从路径提取 mode，自动补齐后缀
    mode = _get_mode(results_path)
    results_path = _ensure_mode_suffix(results_path, mode)
    output_path = _ensure_mode_suffix(output_path, mode)
    results = load_results(results_path)

    if not results:
        print("❌ 没有结果数据，请先运行 eval_pipeline.py")
        return


    # 加载 human_ref 用于对比分析
    human_ref = {}
    if human_ref_path and os.path.exists(human_ref_path):
        with open(human_ref_path, "r", encoding="utf-8") as f:
            for item in json.load(f):
                human_ref[item["id"]] = item

    # 统计
    overalls = [r["overall"] for r in results]
    faithfulness_scores = _dim_scores(results, "faithfulness")
    relevance_scores = _dim_scores(results, "relevance")
    helpfulness_scores = _dim_scores(results, "helpfulness")
    tone_scores = _dim_scores(results, "tone")

    # 最差 3 条
    sorted_results = sorted(results, key=lambda r: r["overall"])
    worst3 = sorted_results[:3]

    # ── 撰写报告 ──
    lines = []
    _w = lines.append

    _w(f"# 客服自动回复质量评估报告\n")
    _w(f"\n> **生成时间**: {__import__('datetime').datetime.now().strftime('%Y-%m-%d %H:%M')}")
    _w(f"\n> **评估样本数**: {len(results)} 条")
    _w(f"\n> **评估模式**: Mock (基于 human_ref 标注映射)")
    _w(f"\n> **方法论**: RAGAS Faithfulness + RAGAS Answer Relevance + G-Eval (Helpfulness & Tone)")
    _w(f"\n---\n")

    # ── 1. 整体摘要 ──
    _w("## 一、整体评估摘要\n")
    _w(f"| 指标 | 分值 | 等级 |")
    _w(f"|------|------|------|")
    _w(f"| **综合均分 (加权)** | **{_mean(overalls)}** | **{_grade_label(_mean(overalls))}** |")
    _w(f"| 最高分 | {max(overalls)} | {_grade_label(max(overalls))} |")
    _w(f"| 最低分 | {min(overalls)} | {_grade_label(min(overalls))} |")
    _w(f"| 标准差 | {_stdev(overalls)} | — |")
    _w("")

    # ── 2. 各指标得分分布 ──
    _w("## 二、各指标得分分布\n")
    _w("| 维度 | 方法论来源 | 均分 | 最高 | 最低 | 标准差 |")
    _w("|------|-----------|------|------|------|--------|")
    _w(f"| **Faithfulness** (事实忠实性) | RAGAS Faithfulness | {_mean(faithfulness_scores)} | {max(faithfulness_scores)} | {min(faithfulness_scores)} | {_stdev(faithfulness_scores)} |")
    _w(f"| **Answer Relevance** (答案相关性) | RAGAS Answer Relevance | {_mean(relevance_scores)} | {max(relevance_scores)} | {min(relevance_scores)} | {_stdev(relevance_scores)} |")
    _w(f"| **Helpfulness** (有用性) | G-Eval CoT Rubric | {_mean(helpfulness_scores)} | {max(helpfulness_scores)} | {min(helpfulness_scores)} | {_stdev(helpfulness_scores)} |")
    _w(f"| **Tone & Empathy** (语气与共情) | G-Eval CoT Rubric | {_mean(tone_scores)} | {max(tone_scores)} | {min(tone_scores)} | {_stdev(tone_scores)} |")
    _w("")

    # 分布直方图 (ASCII)
    _w("### 得分分布可视化\n")
    for dim, scores, label in [
        ("faithfulness", faithfulness_scores, "Faithfulness"),
        ("relevance", relevance_scores, "Answer Relevance"),
        ("helpfulness", helpfulness_scores, "Helpfulness"),
        ("tone", tone_scores, "Tone & Empathy"),
    ]:
        avg = _mean(scores)
        _w(f"**{label}** (均分 {avg})")
        _w(f"```")
        _w(f"  {_score_bar(avg)}")
        _w(f"```")
    _w("")

    # ── 3. 各 case 详细得分 ──
    _w("## 三、各案例详细得分\n")
    _w("| Case | 综合 | F | R | H | T | 自动回复摘要 |")
    _w("|------|------|---|---|---|---|-------------|")
    for r in sorted_results:
        cid = r["case_id"]
        ov = r["overall"]
        f = r["faithfulness"]["score"]
        rv = r["relevance"]["score"]
        h = r["helpfulness"]["score"]
        t = r["tone"]["score"]
        summary = r["auto_reply"][:40].replace("|", "/") + "..."
        _w(f"| {cid} | {ov} | {f} | {rv} | {h} | {t} | {summary} |")
    _w("")

    # ── 4. 最差 3 条深度分析 ──
    _w("## 四、最差 3 条 Case 深度分析\n")
    for rank, r in enumerate(worst3, 1):
        cid = r["case_id"]
        _w(f"### 🔻 第 {rank} 名: {cid} (综合得分: {r['overall']})\n")
        _w(f"**用户问题**: {r['user_question']}\n")
        _w(f"**自动回复**: {r['auto_reply']}\n")
        _w(f"\n| 维度 | 得分 | 分析理由 |")
        _w(f"|------|------|---------|")
        for dim, label in [("faithfulness", "Faithfulness"), ("relevance", "Answer Relevance"),
                           ("helpfulness", "Helpfulness"), ("tone", "Tone & Empathy")]:
            _w(f"| **{label}** | {r[dim]['score']} | {r[dim]['reason']} |")
        _w("")

        # 对比人工标注
        if cid in human_ref:
            ref = human_ref[cid]
            _w(f"\n**人工参考回复**: {ref['human_reference']}\n")
            _w(f"\n**标注员分析**: {ref['annotator_notes']}\n")
        _w("---\n")

    # ── 5. 局限性讨论 ──
    _w("## 五、评估方法的局限性\n")
    _w("""
### 5.1 LLM-as-Judge 的固有偏差
使用 LLM 作为评分器可能引入位置偏差（偏好回复中较早出现的信息）、冗长偏差（偏好更长的回复）、以及自我偏好（偏好与自己风格相近的回复）（G-Eval 论文, 2023）。

### 5.2 Faithfulness 评估缺乏检索上下文
RAGAS Faithfulness 原设计依赖检索上下文作为验证依据。本方案中我们用常识+用户问题上下文替代，可能漏检一些只有内部知识才能发现的错误。

### 5.3 单轮评估局限
客服场景通常是多轮对话，单轮评估无法体现对话管理能力（如追问、澄清等）。

### 5.4 20 条样本量有限
统计意义有限，不能代表全量自动回复的质量分布。

### 5.5 业务知识盲区
评估器不了解内部具体业务规则（如特定优惠券政策、具体商品库存信息等），可能误判"无法回答具体问题"为"没有用"。

### 5.6 语气评估的主观性
每个人对"语气好"的感受不同，评估结果可能存在个体差异。

### 5.7 改进方向
1. 引入多轮对话评估，覆盖追问和上下文感知能力
2. 增加人工抽检环节 (如每条自动回复附加人工复核)
3. A/B 测试对比：自动回复 vs 人工回复的实际转化率
4. 扩大样本量，按场景分类评估（售后/售前/投诉等）
""")

    # ── 6. 回答业务方的 6 个问题 ──
    _w("## 六、对业务方原始问题的回答\n")
    _w("""
### 1. "准确"是什么意思？怎么量化？
准确 = 答案相关 + 事实正确。我们通过两个维度量化：
- **Faithfulness** (25%权重): 回复中的陈述是否可被验证，拆解为原子性陈述逐条检查支持率
- **Answer Relevance** (25%权重): 回复是否直接切题回应用户问题

### 2. "有用"是什么意思？怎么量化？
有用 = 主动帮用户解决问题，而非推诿或泛泛而谈。
- **Helpfulness** (30%权重): 采用 G-Eval 方法，分析回复是"帮用户做"还是"让用户自己去做"

### 3. "语气好"是什么意思？怎么量化？
语气好 = 礼貌、温暖、有共情，能针对用户情绪做出回应。
- **Tone & Empathy** (20%权重): 采用 G-Eval 方法，识别用户情绪并评估回复的共情程度

### 4. "不瞎编"是什么意思？怎么量化？
不瞎编 = 不虚构信息、不编造政策或数据。
- 归入 Faithfulness 指标，通过陈述级验证确保每句话都有依据

### 5. 指标之间的优先级
权重排序: Helpfulness (30%) > Faithfulness (25%) = Relevance (25%) > Tone (20%)
注意: 准确性类 (Faithfulness + Relevance) 合计 50%，是基础底线；有用性单项最高，因为这是我们发现问题最多的维度。

### 6. 局限性有哪些？
见第五章"评估方法的局限性"。
""")

    # 保存
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    report_content = "\n".join(lines)

    # 修复 unescaped 花括号问题: report.py 里用 __import__ 的方式
    # 直接解析时间
    from datetime import datetime
    report_content = report_content.replace(
        "{__import__('datetime').datetime.now().strftime('%Y-%m-%d %H:%M')}",
        datetime.now().strftime('%Y-%m-%d %H:%M')
    )

    with open(output_path, "w", encoding="utf-8") as f:
        f.write(report_content)

    print(f"[完成] 报告已生成: {output_path}")
    return output_path


def main():
    import argparse
    default_results = cfg_get("output.results", "output/eval_results.json")
    default_report = cfg_get("output.report", "output/eval_report.md")
    default_human = cfg_get("data.human_ref", "data/human_ref.json")

    parser = argparse.ArgumentParser(description="生成评估报告")
    parser.add_argument("--results", default=default_results)
    parser.add_argument("--output", default=default_report)
    parser.add_argument("--human-ref", default=default_human)
    args = parser.parse_args()

    generate_report(args.results, args.output, args.human_ref)


if __name__ == "__main__":
    main()
