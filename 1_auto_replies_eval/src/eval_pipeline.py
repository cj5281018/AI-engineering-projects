"""
评估主流水线

加载 auto_replies.json → 逐条评分 (mock/real) → 输出 JSON 结果

配置优先级: CLI 参数 > config.yaml > 硬编码默认值
"""

import argparse
import json
import sys
import os
from typing import Optional

# 确保 src 在路径中
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from config import get as cfg_get
from llm_judge import create_judge, EvalResult


def load_data(path: str) -> list[dict]:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def save_results(results: list[EvalResult], path: str):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump([r.to_dict() for r in results], f, ensure_ascii=False, indent=2)


def _add_mode_suffix(path: str, mode: str) -> str:
    """在文件名中插入 mode 后缀，如 eval_results.json → eval_results_mock.json"""
    base, ext = os.path.splitext(path)
    return f"{base}_{mode}{ext}"


def _ensure_mode_suffix(path: str, mode: str) -> str:
    """如果 path 还没有 mode 后缀，补上，避免 _mock_mock 重复"""
    if not path.endswith(f"_{mode}."):
        return _add_mode_suffix(path, mode)
    return path


def run_pipeline(
    data_path: str = "data/auto_replies.json",
    human_ref_path: str = "data/human_ref.json",
    output_path: str = "output/eval_results.json",
    mode: str = "mock",
) -> list[EvalResult]:
    """
    运行评估流水线。

    Args:
        data_path: auto_replies.json 路径
        human_ref_path: human_ref.json 路径 (仅 mock 模式使用)
        output_path: 结果输出路径
        mode: "mock" 或 "real"

    Returns:
        评估结果列表
    """
    print(f"[加载数据] {data_path}")
    cases = load_data(data_path)

    print(f"[创建评估器] mode={mode}")
    judge_kwargs = {}
    if mode == "mock":
        judge_kwargs["human_ref_path"] = human_ref_path
    judge = create_judge(mode=mode, **judge_kwargs)

    results: list[EvalResult] = []
    for i, case in enumerate(cases, 1):
        cid = case["id"]
        question = case["user_question"]
        reply = case["auto_reply"]
        print(f"  [{i:02d}/20] {cid} ... ", end="", flush=True)
        try:
            result = judge.evaluate(cid, question, reply)
            results.append(result)
            print(f"总分 {result.overall:.2f} (F:{result.faithfulness} R:{result.relevance} H:{result.helpfulness} T:{result.tone})")
        except Exception as e:
            print(f"[失败] {e}")
            # 紧急降级到 mock
            if mode == "real":
                print("    => 降级到 mock 评估器...")
                mock_judge = create_judge(mode="mock", human_ref_path=human_ref_path)
                result = mock_judge.evaluate(cid, question, reply)
                results.append(result)
                print(f"   (mock) 总分 {result.overall:.2f}")

    # 添加 mode 后缀后保存（自动去重）
    output_path = _ensure_mode_suffix(output_path, mode)
    save_results(results, output_path)
    print(f"\n[完成] 评估完成！结果已保存: {output_path}")
    return results


def main():
    # 默认值从 config.yaml 读取
    default_mode = cfg_get("mode", "mock")
    default_data = cfg_get("data.auto_replies", "data/auto_replies.json")
    default_human = cfg_get("data.human_ref", "data/human_ref.json")
    default_output = cfg_get("output.results", "output/eval_results.json")

    parser = argparse.ArgumentParser(description="客服自动回复质量评估流水线")
    parser.add_argument("--mode", choices=["mock", "real"], default=default_mode,
                        help=f"评估模式: mock / real (默认: {default_mode})")
    parser.add_argument("--data", default=default_data,
                        help=f"auto_replies.json 路径")
    parser.add_argument("--human-ref", default=default_human,
                        help=f"human_ref.json 路径 (mock 模式使用)")
    parser.add_argument("--output", default=default_output,
                        help=f"结果 JSON 输出路径")
    args = parser.parse_args()

    run_pipeline(
        data_path=args.data,
        human_ref_path=args.human_ref,
        output_path=args.output,
        mode=args.mode,
    )


if __name__ == "__main__":
    main()
