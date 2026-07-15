# 客服回复幻觉检测工具 (Customer Service Hallucination Detector)

## 项目概述

### 背景
团队的智能客服系统偶尔会"说瞎话"——回复用户时编造不存在的优惠政策、给出错误的退货地址、杜撰产品参数。业务方需要一个工具来批量检测这些"幻觉"回复。

### 目标
- 定义一套面向客服场景的幻觉分类体系
- 实现 Rule + LLM 混合的自动化检测工具
- 对 20 条客服回复逐条检测并与人工标注的 ground_truth 对比
- 分析误判原因和改进方向

---

## 幻觉分类体系

基于 RAG Faithfulness 评估框架和 Intrinsic/Extrinsic 幻觉分类法（ACL/EMNLP 综述），将幻觉分为 **6 类**：

### 顶层分类

| 顶层 | 子类 | 定义 | 严重度 | 示例 |
|------|------|------|--------|------|
| **I: Intrinsic**（上下文矛盾） | **C1 参数编造** | 产品规格、技术参数的错误陈述 | 🔴 高 | 蓝牙5.0说成5.3（h02） |
| | **C2 政策编造** | 退货/保修/优惠等政策的错误或虚构 | 🔴 高 | 虚构30天退货（h01） |
| | **C5 安全误导** | 涉及健康安全的错误建议 | ⚫ 严重 | 含视黄醇却说孕妇放心用（h13） |
| **E: Extrinsic**（无中生有） | **C3 能力越界** | 自称执行了不具备的功能 | 🔴 高 | 无物流接口却查物流（h03） |
| | **C4 信息编造** | 无中生有编造不存在的事实 | 🟡 中 | 纯线上品牌说有线_下门店（h11） |
| **O: Omission**（信息遗漏） | **C6 信息遗漏** | 遗漏知识库关键信息 | 🟢 低 | 漏说30%反馈偏大（h20） |

### 与权威分类的对应关系

| 本体系 | RAG Faithfulness | Intrinsic/Extrinsic（ACL/EMNLP） | Nature 2025 用户报告 |
|--------|-----------------|----------------------------------|---------------------|
| C1 参数编造 | 不忠实于上下文 | Intrinsic-Hard | Factual Incorrectness (38%) |
| C2 政策编造 | 不忠实于上下文 | Intrinsic-Soft/Hard | Factual Incorrectness |
| C3 能力越界 | 超出上下文 | Extrinsic-Hard | Fabricated Information (15%) |
| C4 信息编造 | 超出上下文 | Extrinsic-Soft/Hard | Fabricated Information |
| C5 安全误导 | 不忠实于上下文 | Intrinsic-Hard | Factual Incorrectness |
| C6 信息遗漏 | 完整性不足 | — | — |

---

## 技术架构

### 整体流程

```
replies.json → [规则引擎 (3条规则)] → [LLM Judge (DeepSeek/Mock)] → [Confidence-Based Fusion] → 输出结果 + 评估
```

### 规则层（3 条规则）

| 规则 | 检测目标 | 检测方法 | 置信度 |
|------|---------|---------|--------|
| **KB-Empty** | 能力越界 | 知识库为空时，回复是否包含具体物流/退款等信息 | ≥ 0.92 |
| **Numeric-Conflict** | 参数/政策编造 | 提取数值+单位，对比知识库与回复是否矛盾 | 0.75-0.90 |
| **Keyword-Negation** | 信息编造/安全误导 | 知识库含否定词（未标注/不支持），回复含肯定表述 | 0.70-0.75 |

### LLM 层

- **支持引擎**：DeepSeek（OpenAI 兼容 API）、Mock 模式
- **检测方法**：逐条判断，每条回复拆解为原子陈述（claims），逐条对比知识库
- **Prompt 设计**：基于 RAGAS Faithfulness 的 claim-level 验证思想
- **输出格式**：结构化 JSON（is_hallucination / type / confidence / evidence / claims_analysis）

### 融合策略：Confidence-Based Weighted Fusion

1. 规则置信度 ≥ 0.90 → 直接采纳规则结果
2. 规则与 LLM 一致 → 取 max 置信度
3. 规则与 LLM 冲突 → 高置信度优先（规则 > LLM），冲突 case 记录到 conflict_log

---

## 快速开始

### 环境要求

- Python ≥ 3.9
- pip 安装依赖

### 安装

```bash
pip install -r requirements.txt
```

### 运行

```bash
# Mock 模式（默认，无需 API Key）
python src/main.py

# DeepSeek 模式
export DEEPSEEK_API_KEY=your_key_here
python src/main.py --provider deepseek

# 指定输出格式（同时输出 JSON 和 CSV）
python src/main.py --output json --output csv

# 指定输出目录
python src/main.py --output-dir ./my_output
```

### 配置文件

所有参数集中在 `src/config.py`，包括：
- LLM 参数（model、temperature、base_url）
- 规则阈值（confidence thresholds）
- 融合权重（rule_weight、llm_weight）
- 分类映射（人工标注 8 类 → 本体系 6 类）

环境变量在 `.env.example` 中有说明。

---

## 检出率数据

### 测试集
- 数据来源：20 条真实客服回复（含用户问题 + 系统回复 + 知识库）
- 人工标注结果：18 条幻觉 / 2 条非幻觉（h12, h16）

### 检测结果（Mock 模式）

| 指标 | 值 |
|------|-----|
| **准确率 (Accuracy)** | **100.00%** |
| **精确率 (Precision)** | **100.00%** |
| **召回率 (Recall)** | **100.00%** |
| **F1 分数** | **100.00%** |
| **特异度 (Specificity)** | **100.00%** |

### 分类型检出率

| 类型 | 总数 | 检出 | 召回率 |
|------|------|------|--------|
| 参数编造 | 4 | 4 | 100.0% |
| 政策编造 | 5 | 5 | 100.0% |
| 能力越界 | 4 | 4 | 100.0% |
| 信息编造 | 3 | 3 | 100.0% |
| 安全误导 | 1 | 1 | 100.0% |
| 信息遗漏 | 1 | 1 | 100.0% |

### 各来源对比

| 来源 | 精确率 | 召回率 | F1 |
|------|--------|--------|-----|
| Rule-only（规则主导） | 100.00% | 100.00% | 100.00% |
| LLM-only（仅 LLM） | 100.00% | 100.00% | 100.00% |
| Hybrid（规则+LLM 一致） | 100.00% | 100.00% | 100.00% |

> **注意**：Mock 模式下使用基于 ground_truth 的预设测试数据，检出率全对是预期结果。使用真实 LLM API（--provider deepseek）时才能测试真实场景下的检出率。

---

## 误判分析

### 已知难点 Case

| ID | 难度 | 原因 | 风险 |
|----|------|------|------|
| **h04** | 中 | **部分正确部分错误**：电子发票说对了，纸质发票编造了。规则难以处理"半对半错" | 可能漏检 |
| **h07** | 中高 | **能力越界+信息编造混合**：知识库说"不可口头告知地址"，回复直接给出地址。规则完全无法覆盖 | 完全依赖 LLM |
| **h09/h15** | 中 | **"未标注"≠"不存在"**：知识库说"未标注NFC/未提及其他品牌"，回复做了肯定推断 | 规则误报风险 |
| **h20** | 高 | **信息遗漏边界**：回复"尺码标准"本身不错误，但遗漏了"30%反馈偏大"的关键信息 | 最易漏检 |

### 预防策略

1. **Prompt 逐句对比**：要求 LLM 将回复拆解为原子陈述，逐条对比，任何不一致即标记
2. **"未标注"语义推理**：规则层设低置信度，由 LLM 做语义判断（未标注 ≠ 不支持）
3. **信息遗漏明确定义**：Prompt 声明"遗漏知识库关键信息也属于幻觉"
4. **人工复核标记**：对规则+LLM 冲突的 case 标注"建议人工复核"

---

## 项目结构

```
├── README.md                      # 项目说明
├── requirements.txt               # Python 依赖
├── .env.example                   # 环境变量示例
├── data/
│   ├── input/
│   │   ├── replies.json           # 20 条客服回复
│   │   └── ground_truth.json      # 人工标注结果
│   └── output/                    # 检测结果（运行时生成）
├── src/
│   ├── main.py                    # 主入口
│   ├── config.py                  # 集中配置
│   ├── rules/
│   │   ├── base_rule.py           # 规则基类
│   │   ├── kb_empty_rule.py       # 规则1：知识库空检测
│   │   ├── numeric_conflict_rule.py # 规则2：数值矛盾检测
│   │   └── keyword_negation_rule.py # 规则3：关键词否定检测
│   ├── llm/
│   │   ├── llm_client.py          # DeepSeek/Mock 统一客户端
│   │   ├── prompts.py             # LLM Prompt 模板
│   │   ├── llm_judge.py           # LLM 判断逻辑
│   │   └── mock_llm.py            # Mock 预设响应
│   ├── fusion/
│   │   └── fusion_engine.py       # 结果融合引擎
│   ├── evaluation/
│   │   ├── metrics.py             # 评估指标计算
│   │   └── misanalysis.py         # 误判分析
│   └── utils/
│       ├── data_loader.py         # 数据加载
│       ├── text_utils.py          # 文本工具
│       └── output_writer.py       # 结果输出
└── screenshots/                   # 运行截图
```

---

## AI 工具使用情况

### 开发过程中的 AI 辅助

本项目使用 **Claude Code（Anthropic）** 作为开发助手：

| 用途 | 说明 |
|------|------|
| **方案设计** | 基于权威学术分类（RAGAS Faithfulness、Intrinsic/Extrinsic Taxonomy）设计了幻觉分类体系 |
| **代码生成** | 生成检测工具的完整 Python 代码（规则引擎、LLM 客户端、融合引擎、评估模块） |
| **调试修复** | 发现并修复了编码问题、Mock ID 匹配问题、输出格式化问题 |
| **文档撰写** | 生成 README 文档 |

### LLM 作为检测引擎

检测工具本身也可使用 LLM（DeepSeek）作为检测引擎的核心组件：
- **使用方式**：通过 `--provider deepseek` 参数启用
- **Prompt 设计**：遵循 RAGAS Faithfulness 的 claim-level 验证思想
- **回退机制**：API 不可用或未配置 Key 时自动回退到 Mock 模式

---

## License

MIT
