"""
LLM Judge — 评估器抽象接口 + MockJudge / RealJudge 双实现

支持两种模式:
- mock: 基于 human_ref.json 的手工标注分析，映射为量化评分
- real: 调用真实 LLM API (OpenAI / Anthropic 兼容) 进行评分
"""

import json
import re
from abc import ABC, abstractmethod
from typing import Optional

from config import get as cfg_get

# ---------------------------------------------------------------------------
# 评分结果数据类
# ---------------------------------------------------------------------------

class EvalResult:
    """一条 auto_reply 的完整评估结果"""
    def __init__(self, case_id: str, user_question: str, auto_reply: str,
                 faithfulness: float, faithfulness_reason: str,
                 relevance: float, relevance_reason: str,
                 helpfulness: float, helpfulness_reason: str,
                 tone: float, tone_reason: str):
        self.case_id = case_id
        self.user_question = user_question
        self.auto_reply = auto_reply
        self.faithfulness = faithfulness
        self.faithfulness_reason = faithfulness_reason
        self.relevance = relevance
        self.relevance_reason = relevance_reason
        self.helpfulness = helpfulness
        self.helpfulness_reason = helpfulness_reason
        self.tone = tone
        self.tone_reason = tone_reason

    @property
    def overall(self) -> float:
        """加权综合得分 (权重: Faithfulness 25%, Relevance 25%, Helpfulness 30%, Tone 20%)"""
        return (
            self.faithfulness * 0.25
            + self.relevance * 0.25
            + self.helpfulness * 0.30
            + self.tone * 0.20
        )

    def to_dict(self) -> dict:
        return {
            "case_id": self.case_id,
            "user_question": self.user_question,
            "auto_reply": self.auto_reply,
            "faithfulness": {"score": self.faithfulness, "reason": self.faithfulness_reason},
            "relevance": {"score": self.relevance, "reason": self.relevance_reason},
            "helpfulness": {"score": self.helpfulness, "reason": self.helpfulness_reason},
            "tone": {"score": self.tone, "reason": self.tone_reason},
            "overall": round(self.overall, 2),
        }


# ---------------------------------------------------------------------------
# 抽象基类
# ---------------------------------------------------------------------------

class BaseJudge(ABC):
    """评估器基类"""

    @abstractmethod
    def evaluate(self, case_id: str, user_question: str, auto_reply: str) -> EvalResult:
        ...


# ---------------------------------------------------------------------------
# MockJudge — 基于 human_ref 标注映射的模拟评分
# ---------------------------------------------------------------------------

class MockJudge(BaseJudge):
    """
    Mock 评估器：利用 human_ref.json 的 annotator_notes 做定性→定量映射。

    映射规则设计说明:
    - 每条标注被解析为关键词匹配 → 各维度的扣分/加分
    - 基础分为 4.0，根据标注中的批评点扣分，肯定点加分
    """

    # 标注关键词 → (维度, 分数调整)
    _KEYWORD_RULES = [
        # ---- Helpfulness 相关 ----
        (r"推给用户|甩锅|让用户自己[去找查看]|用户自己[去操作查看]|没有帮用户", "helpfulness", -2.0),
        (r"没有针对性|通用[的]?[建议说明]|泛泛而谈|偏通用", "helpfulness", -1.0),
        (r"没有实质帮助|没有解决", "helpfulness", -2.0),
        (r"主动帮用户|直接协助|直接[查操作处理]|帮您查|我来帮您", "helpfulness", +0.5),
        (r"追问|给[了]?针对性", "helpfulness", +0.5),

        # ---- Relevance 相关 ----
        (r"答非所问|没有回答|没有回应[了]?用户", "relevance", -2.0),
        (r"通用[的]?[回答说明]|没有针对[性]?[该具体]", "relevance", -1.0),
        (r"[完全切题精确]|直接回应", "relevance", +0.5),

        # ---- Faithfulness 相关 ----
        (r"正确[的]?[^没]|没有错误|信息准确|规则说明正确", "faithfulness", +0.5),
        (r"[虚构编造]|信息有误|事实错误|不准确", "faithfulness", -2.0),

        # ---- Tone 相关 ----
        (r"[缺乏没有]共情|机械|模板[化]?|敷衍|不够[体贴温暖]|冰冷|冷淡", "tone", -1.5),
        (r"情绪[安抚]?[不安害怕]|需要[安抚]?[关注照顾].*情绪|用户.*情绪", "tone", -1.0),
        (r"[温暖真诚]|[体贴耐心]|热情", "tone", +0.5),
        (r"[道歉]?让您.*[等待不便]|非常抱歉|理解您.*[感受情绪]", "tone", +0.5),

        # ---- 综合高权重信号 ----
        (r"回答.*尚可|自动回复.*[尚可不错]|基本正确|处理方式基本合理", "helpfulness", +0.5),
        (r"属于.*答非所问", "relevance", -2.5),
        (r"又没有帮用户查|没有帮用户实际[排查查询]", "helpfulness", -1.5),
    ]

    # 每个维度的基线分 (1-5 分制)
    _BASE_SCORE = 4.0
    _MIN_SCORE = 1.0
    _MAX_SCORE = 5.0

    def __init__(self, human_ref_path: str = "data/human_ref.json"):
        with open(human_ref_path, "r", encoding="utf-8") as f:
            self._human_ref = {item["id"]: item for item in json.load(f)}

    def evaluate(self, case_id: str, user_question: str, auto_reply: str) -> EvalResult:
        notes = self._get_notes(case_id)
        scores = {"faithfulness": self._BASE_SCORE, "relevance": self._BASE_SCORE,
                  "helpfulness": self._BASE_SCORE, "tone": self._BASE_SCORE}
        reasons = {"faithfulness": [], "relevance": [], "helpfulness": [], "tone": []}

        # 应用关键词规则
        for pattern, dim, delta in self._KEYWORD_RULES:
            if re.search(pattern, notes, re.IGNORECASE):
                scores[dim] += delta
                reasons[dim].append(f"[规则] 匹配: 「{pattern}」 → {delta:+.1f}")

        # 四舍五入并钳制
        final = {}
        for dim in ["faithfulness", "relevance", "helpfulness", "tone"]:
            raw = round(scores[dim], 1)
            final[dim] = max(self._MIN_SCORE, min(self._MAX_SCORE, raw))
            if not reasons[dim]:
                reasons[dim].append("[规则] 未匹配到关键规则，取基线分")

        return EvalResult(
            case_id=case_id,
            user_question=user_question,
            auto_reply=auto_reply,
            faithfulness=final["faithfulness"],
            faithfulness_reason=" | ".join(reasons["faithfulness"]),
            relevance=final["relevance"],
            relevance_reason=" | ".join(reasons["relevance"]),
            helpfulness=final["helpfulness"],
            helpfulness_reason=" | ".join(reasons["helpfulness"]),
            tone=final["tone"],
            tone_reason=" | ".join(reasons["tone"]),
        )

    def _get_notes(self, case_id: str) -> str:
        ref = self._human_ref.get(case_id, {})
        return ref.get("annotator_notes", "")


# ---------------------------------------------------------------------------
# RealJudge — 调用真实 LLM API 进行评分
# ---------------------------------------------------------------------------

class RealJudge(BaseJudge):
    """
    真实 LLM 评估器。

    支持:
    - OpenAI 兼容 API (GPT-4o, DeepSeek 等)
    - Anthropic Claude API

    配置方式: config.yaml → llm 段，或通过环境变量 LLM_API_KEY 传入 key
    """

    _F_SYSTEM_PROMPT = """你是一个客服回复质量评估专家。你需要严格、客观地对自动客服回复进行评分。

你需要从 4 个维度评分，每个维度 1-5 分。评分要严厉，不要一律给高分——不好的回复要打低分。

## 维度 1: Faithfulness (事实忠实性)
评估回复中的每一条陈述是否事实正确、有无虚构或编造信息。
参考行业标准: RAGAS Faithfulness — 拆解陈述并逐一验证。
- 5 = 所有陈述完全符合事实
- 3 = 部分陈述笼统但无明显错误
- 1 = 存在虚构或严重事实错误

## 维度 2: Answer Relevance (答案相关性)
回复是否直接切题地回答了用户的问题。
参考行业标准: RAGAS Answer Relevance。
- 5 = 完全切题，精确回应
- 3 = 部分相关但有偏
- 1 = 完全不相关，答非所问

## 维度 3: Helpfulness (有用性/可操作性)
回复是主动帮用户解决问题，还是给通用建议推给用户自己操作？
参考行业标准: G-Eval Chain-of-Thought Rubric。
- 5 = 主动解决问题，提供明确路径
- 3 = 信息正确但偏通用模板
- 1 = 完全没有解决用户问题

## 维度 4: Tone & Empathy (语气与共情)
语气是否礼貌、温暖、有共情？
- 5 = 非常温暖真诚，情绪安抚到位
- 3 = 基本礼貌但偏机械
- 1 = 语气不当，缺乏基本礼貌

## 输出格式
先逐步推理分析，然后输出以下 JSON 结构:
```json
{
  "faithfulness": {"score": 4, "reason": "..."},
  "relevance": {"score": 4, "reason": "..."},
  "helpfulness": {"score": 3, "reason": "..."},
  "tone": {"score": 3, "reason": "..."}
}
```"""

    _F_USER_TEMPLATE = """【用户问题】
{question}

【自动回复】
{reply}

请从 Faithfulness、Answer Relevance、Helpfulness、Tone & Empathy 四个维度评分。"""

    # 各 LLM 提供商的默认配置
    _PROVIDER_DEFAULTS = {
        "deepseek":  {"base_url": "https://api.deepseek.com/v1", "model": "deepseek-chat"},
    }

    def __init__(self):
        # 从 config.yaml 读取
        judge_type = cfg_get("llm.type", "openai").lower()
        api_key = cfg_get("llm.api_key", "")
        base_url = cfg_get("llm.base_url", "") or None
        model = cfg_get("llm.model", "") or None

        # 获取提供商默认值
        defaults = self._PROVIDER_DEFAULTS.get(judge_type, self._PROVIDER_DEFAULTS["deepseek"])
        base_url = base_url or defaults["base_url"]
        model = model or defaults["model"]

        if judge_type == "anthropic":
            self._init_anthropic(api_key, model)
        elif judge_type == "deepseek":
            self._init_deepseek(api_key, base_url, model)
        else:
            self._init_openai(api_key, base_url, model)

    def _init_deepseek(self, api_key: str, base_url: str, model: str):
        try:
            from openai import OpenAI
        except ImportError:
            raise ImportError("openai 未安装。使用 DeepSeek 需要: pip install openai")
        self._client = OpenAI(api_key=api_key or None, base_url=base_url)
        self._model = model
        self._backend = "deepseek"


    def evaluate(self, case_id: str, user_question: str, auto_reply: str) -> EvalResult:
        prompt = self._F_USER_TEMPLATE.format(question=user_question, reply=auto_reply)
        raw = self._call_llm(prompt)
        data = self._parse_response(raw)

        return EvalResult(
            case_id=case_id,
            user_question=user_question,
            auto_reply=auto_reply,
            faithfulness=float(data["faithfulness"]["score"]),
            faithfulness_reason=data["faithfulness"].get("reason", ""),
            relevance=float(data["relevance"]["score"]),
            relevance_reason=data["relevance"].get("reason", ""),
            helpfulness=float(data["helpfulness"]["score"]),
            helpfulness_reason=data["helpfulness"].get("reason", ""),
            tone=float(data["tone"]["score"]),
            tone_reason=data["tone"].get("reason", ""),
        )

    def _call_llm(self, user_prompt: str) -> str:
        messages = [
            {"role": "system", "content": self._F_SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt},
        ]
        kwargs = dict(
            model=self._model,
            messages=messages,
            max_tokens=1024,
            temperature=0.0,
        )

        # OpenAI / DeepSeek 兼容
        if self._backend == "deepseek":
            # DeepSeek 不支持 response_format={"type": "json_object"}
            resp = self._client.chat.completions.create(**kwargs)
        else:
            resp = self._client.chat.completions.create(
                **kwargs, response_format={"type": "json_object"}
            )
        return resp.choices[0].message.content

    @staticmethod
    def _parse_response(raw: str) -> dict:
        # 尝试提取 JSON 块
        match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", raw, re.DOTALL)
        if match:
            raw = match.group(1)
        return json.loads(raw)


# ---------------------------------------------------------------------------
# Factory
# ---------------------------------------------------------------------------

def create_judge(mode: str = "mock", **kwargs) -> BaseJudge:
    """工厂函数: 根据 mode 创建评估器"""
    if mode == "real":
        return RealJudge(**kwargs)
    return MockJudge(**kwargs)
