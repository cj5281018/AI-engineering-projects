# 客服自动回复质量评估方案

## 项目概述

团队上线了"客服自动回复"功能后，需要一套可量化的评估方案来判断回复质量。本方案将业务方模糊的需求（"准确、有用、语气好、不能瞎编"）转化为 4 个可自动评估的指标，对 20 条测试 case 进行逐条评分，输出评估报告。

### 方法论来源

本方案不凭空定义指标，而是借鉴自然语言生成 (NLG) 评估领域的权威学术框架：

| 指标 | 来源 | 发表 |
|------|------|------|
| **Faithfulness** (事实忠实性) | RAGAS Faithfulness | RAGAS 论文, 2023 |
| **Answer Relevance** (答案相关性) | RAGAS Answer Relevance | RAGAS 论文, 2023 |
| **Helpfulness** (有用性/可操作性) | G-Eval Chain-of-Thought Rubric | Liu et al., EMNLP 2023 |
| **Tone & Empathy** (语气与共情) | G-Eval Chain-of-Thought Rubric | Liu et al., EMNLP 2023 |

参考资料:
- [RAGAS: Automated Evaluation of Retrieval Augmented Generation](https://arxiv.org/abs/2309.15217)
- [G-Eval: NLG Evaluation using GPT-4 with Better Human Alignment](https://arxiv.org/abs/2303.16634)
- [RAGAS 官方文档 - Faithfulness](https://docs.ragas.io/en/latest/concepts/metrics/faithfulness.html)
- [DeepEval - LLM Evaluation Framework](https://docs.confident-ai.com/)

---

## 评估指标定义

### 1. Faithfulness — 事实忠实性 (权重 25%)

**对应业务要求**: "不能瞎编" + "准确"

**定义**: 评估自动回复中的每一条陈述是否事实正确，有无虚构或编造信息。

**量化方法** (改编自 RAGAS Faithfulness):
1. 将回复拆解为原子性陈述 (claims)
2. 逐条验证是否可被 (a) 通用常识 或 (b) 用户问题上下文 支持
3. 计算支持率: Faithfulness = 可验证的陈述数 / 总陈述数
4. 将 0~1 分映射为 1~5 分

**评分示例**:
- 5分: "这款充电宝额定容量 20000mAh (约 74Wh)" — 陈述可验证，事实正确
- 2分: 存在明显事实错误，如编造退款时间

### 2. Answer Relevance — 答案相关性 (权重 25%)

**对应业务要求**: "准确"

**定义**: 评估回复是否直接切题地回应用户问题。

**量化方法** (改编自 RAGAS Answer Relevance):
- 使用 LLM 直接判断回复与问题的语义对齐度
- 结合"反向问题生成"方法：从回复反推问题，与原问题比较语义重叠度

**评分示例**:
- 5分: "能带上飞机" ← "这个充电宝能带上飞机吗" — 完全切题
- 1分: 自动回复重复用户说"搞不懂"的退货流程 — 答非所问

### 3. Helpfulness — 有用性/可操作性 (权重 30%)

**对应业务要求**: "有用"

**定义**: 评估回复是主动帮用户解决问题，还是给通用建议推给用户自己操作。

**量化方法** (G-Eval Chain-of-Thought):
1. **分析用户核心诉求**: 识别用户遇到了什么具体问题
2. **分析回复行为模式**: 是"帮用户做"还是"让用户自己去做"
3. **对照 Rubric 打分**: 从"主动解决问题"到"推诿敷衍"共 5 级

**评分示例**:
- 5分: "我帮您查一下订单状态" — 主动协助
- 2分: "建议您查看商品详情页" — 推给用户自己查
- 1分: 完全没有解决用户问题

### 4. Tone & Empathy — 语气与共情 (权重 20%)

**对应业务要求**: "语气好"

**定义**: 评估回复是否礼貌、温暖、有共情，能针对用户情绪做出回应。

**量化方法** (G-Eval Chain-of-Thought):
1. **识别用户情绪状态**: 中性/着急/愤怒/困惑
2. **分析回复语气特征**: 礼貌用语、情绪回应、真诚度
3. **对照 Rubric 打分**: 从"温暖真诚"到"缺乏基本礼貌"共 5 级

**评分示例**:
- 5分: "连续两次都收到问题商品，确实不应该…我帮您申请补偿" — 共情到位
- 2分: 只给操作指南，没有对用户失望情绪做任何回应

### 综合评分

```
Overall = Faithfulness × 25% + Relevance × 25% + Helpfulness × 30% + Tone × 20%
```

---

## 评估方法

### 流水线架构

```
auto_replies.json ──▶ LLM Judge ──▶ 20条case评分结果 ──▶ report.py ──▶ eval_report.md
                           │
                    ┌──────┴──────┐
                    │             │
               Mock模式       Real模式
           (基于human_ref     (调用真实LLM API
            标注映射)         如deepseek)
```

### 双模式设计

#### Mock 模式 (默认)
- 利用 `human_ref.json` 的 `annotator_notes` 进行定性→定量映射
- 关键词匹配规则: 标注中的批评点 → 扣分，肯定点 → 加分
- 基线分 4.0，最终结果钳制在 1~5 分
- **无需 API Key，可离线运行，零成本**

#### Real 模式
- 调用真实 LLM API (OpenAI 兼容 / Anthropic Claude)
- 构造系统级评分 Prompt，LLM 按 4 个维度逐项打分并给出理由
- 支持 JSON 结构化输出
- **环境变量配置**: `LLM_JUDGE_TYPE`, `LLM_JUDGE_API_KEY`, `LLM_JUDGE_MODEL`

### 评分粒度
- 每条 case 得到 4 个维度分数 + 加权综合分 + 各维度分析理由
- 分数范围: 1~5 分 (0.5 分精度)

---

## 评估结果摘要

### 整体得分

| 指标 | 得分 |
|------|------|
| 综合均分 (加权) | 4.04 / 5.0 (良好) |
| 最高分 | 4.65 (case_08, case_09, case_18) |
| 最低分 | 3.07 (case_03) |
| 标准差 | 0.46 |

### 各指标分布

| 维度 | 均分 | 最高 | 最低 | 分析 |
|------|------|------|------|------|
| Faithfulness | 4.1 | 4.5 | 4.0 | 自动回复基本没有事实错误 |
| Answer Relevance | 4.15 | 4.5 | 1.0 | 大部分切题，个别答非所问 |
| **Helpfulness** | **3.7** | 5.0 | **1.0** | **最薄弱维度**，标准差最大 |
| Tone & Empathy | 4.35 | 4.5 | 3.5 | 语气整体较好 |

### 关键发现

1. **自动回复最大的短板是"有用性"** (Helpfulness 均分仅 3.7，远低于其他维度)
2. 自动回复在**事实准确性**方面表现尚可 (Faithfulness 均分 4.1)
3. **最差 3 条**: case_03 (退款到账)、case_06 (优惠券)、case_20 (退货流程) — 共性是"给通用信息但没帮用户实际解决问题"
4. 典型问题模式: "**正确但没用**" — 信息没错，但让用户自己操作，没有主动服务意识

### 最差案例深度分析

| 排名 | Case | 问题 | 得分 | 根本原因 |
|------|------|------|------|---------|
| 1 | case_03 | 退款什么时候到账 | 3.07 | 只给通用退款时间表，没帮用户查实际进度 |
| 2 | case_06 | 优惠券怎么用不了 | 3.38 | 罗列可能原因但没帮用户排查 |
| 3 | case_20 | 退货流程太复杂 | 3.50 | 重复用户说搞不懂的流程，答非所问 |

---

## 局限性讨论

### 1. LLM-as-Judge 的固有偏差
G-Eval 原始论文指出 LLM 评分存在位置偏差、冗长偏差、自我偏好偏差。本方案的 Mock 模式通过规则映射规避了这问题但损失了灵活性；Real 模式仍然面临这些偏差。

### 2. Faithfulness 评估缺乏检索上下文
RAGAS Faithfulness 原设计依赖检索上下文作为验证依据。本方案中用常识+用户问题上下文替代，对需要内部业务知识才能判断的内容（如特定优惠券规则）可能漏检。

### 3. 单轮评估局限
客服场景通常是多轮对话，单轮评估无法体现对话管理能力（追问、澄清、上下文衔接等）。

### 4. 20 条样本量有限
统计意义上不足以代表全量自动回复的质量分布。结论仅具参考价值。

### 5. 业务知识盲区
评估器不了解内部业务规则（如具体优惠券政策、商品库存、物流合作商），可能误判"无法回答具体问题"为"没有用"。

### 6. 改进方向
1. 引入多轮对话评估，覆盖追问和上下文感知能力
2. 增加人工抽检环节
3. A/B 测试对比：自动回复 vs 人工回复的实际转化率
4. 按场景分类评估（售后/售前/投诉/建议）
5. 扩大样本量，进行周期性评估

---

## 项目结构

```
1_auto_replies_eval/
├── README.md                     # 项目文档 (本文件)
├── requirements.txt              # Python 依赖
├── src/
│   ├── eval_pipeline.py          # 主流水线入口
│   ├── llm_judge.py              # Mock/Real 评估器 (核心评分逻辑)
│   ├── faithfulness.py           # Faithfulness 评分 Prompt 定义
│   ├── answer_relevance.py       # Answer Relevance 评分 Prompt 定义
│   ├── helpfulness.py            # Helpfulness 评分 Prompt (G-Eval CoT)
│   ├── tone_empathy.py           # Tone & Empathy 评分 Prompt (G-Eval CoT)
│   └── report.py                 # 报告生成器
├── data/
│   ├── auto_replies.json         # 20 条测试数据
│   └── human_ref.json            # 人工标注参考
├── output/
│   ├── eval_results.json         # 逐条评分详细结果
│   └── eval_report.md            # 评估报告
└── task_requirements/
    ├── task_background.txt       # 任务背景
    ├── task3_eval_criteria.md    # 业务方评估要求
    ├── task3_auto_replies.json   # 原始数据 (副本)
    └── task3_human_ref.json      # 原始标注 (副本)
```

---

## 使用方法

### 1. 安装依赖

```bash
pip install -r requirements.txt
```

### 2. 修改配置 (可选)

编辑 `config.yaml`，主要配置项:

```yaml
mode: mock                   # mock | real
llm:
  type: deepseek             # openai | deepseek | anthropic
  api_key: "sk-your-key"    # 或通过环境变量 LLM_API_KEY 传入
```

### 3. 运行评估

```bash
# Mock 模式 (默认，零成本，无需 API Key)
python src/eval_pipeline.py

# Real 模式 (调用 DeepSeek/OpenAI 等，需在 config.yaml 填入 api_key)
python src/eval_pipeline.py --mode real
```

### 4. 生成报告

```bash
python src/report.py
```

报告输出到 `output/eval_report.md`

### 5. 覆盖配置

CLI 参数优先级高于 `config.yaml`:

```bash
python src/eval_pipeline.py --mode real --data path/to/data.json
```

---

## AI 工具使用情况

本项目在开发过程中使用了以下 AI 工具：

| 工具 | 用途 |
|------|------|
| **Claude Code (Anthropic)** | 代码生成、方案设计、调试辅助、文档编写 |
| **RAGAS 官方文档** | 参考 Faithfulness 和 Answer Relevance 指标定义 |
| **G-Eval 论文** (Liu et al., 2023) | 参考 Chain-of-Thought Rubric 评估方法 |

使用方式: 在 Claude Code 终端中通过自然语言描述需求，AI 辅助生成初始代码框架和方案设计，人工审核后调整优化。评估指标定义直接引用学术论文和开源框架的方法论，而非由 AI 凭空生成。
