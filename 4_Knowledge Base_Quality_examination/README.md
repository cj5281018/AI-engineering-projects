# 知识库质量检测工具

## 概述

智能客服知识库经过一年多积累，有 500+ 条 FAQ，但从未系统维护。本工具自动扫描知识库中的 FAQ 条目，基于**国际权威框架**定义问题分类体系，通过**规则引擎 + LLM 双轨检测**找出问题条目，生成结构化治理报告。

### 核心能力

- **双轨检测**：规则引擎处理确定性检测（过时/空值/重复/矛盾），LLM 处理语义检测（专业度/语义矛盾/建议生成）
- **双模式支持**：Mock 模式（无需 API Key）和 DeepSeek API 模式（真实 LLM 检测）
- **双格式报告**：JSON 结构化数据 + Markdown 可读报告
- **三级优先级**：P0（立即处理）/ P1（尽快处理）/ P2（常规优化）

---

## 问题分类体系

本工具的问题分类体系参考了以下权威框架：

| 参考框架 | 来源 | 核心维度 |
|---------|------|---------|
| **RAG Triad** | RAGAS / TruLens | Context Relevance → Faithfulness → Answer Relevance |
| **数据质量四维模型** | Atlan / Knowmax / Gartner | Accuracy + Freshness + Completeness + Consistency |
| **KG 异常分类 TAXO** | Senaratne et al.（学术论文） | Redundant → Inconsistent → Deficient → Invalid |
| **RAG 数据质量挑战** | ICIS 2025 | 15 个数据质量维度在 RAG 4 阶段的传播机制 |
| **内容分级审核** | Knowmax / Ariglad | Tier 1（每月）/ Tier 2（每季）/ Tier 3（每半年） |

### 8 类问题定义

| 分类 ID | 分类名称 | 对应权威框架 | 严重度 | 检测方式 |
|---------|---------|-------------|--------|---------|
| `contradictory_business` | 与业务规则矛盾 | Faithfulness × TAXO-Inconsistent | **P0 高** | 规则引擎 |
| `empty_answer` | 空答案 | Completeness × TAXO-Deficient | **P0 高** | 规则引擎 |
| `contradictory_internal` | 条目间矛盾 | Consistency × TAXO-Inconsistent | **P1 高** | 规则引擎 + LLM |
| `outdated` | 内容过时 | Freshness × TAXO-Invalid | **P1 中** | 规则引擎 |
| `duplicate` | 重复条目 | Completeness × TAXO-Redundant | **P1 中** | 规则引擎 |
| `unprofessional` | 表达不专业 | Accuracy | **P2 中** | LLM |
| `missing_coverage` | 覆盖缺失 | Completeness × TAXO-Deficient | **P2 中** | LLM |
| `incomplete` | 回答不完整 | Completeness | **P2 低** | 规则引擎 |

---

## 检测方法

### 整体架构

```
┌─────────────────────────────────────────────────────────────┐
│                        main.py (CLI入口)                      │
├─────────────────────────────────────────────────────────────┤
│  data/loader.py     →  加载 kb_articles.json               │
│  rules/parser.py    →  解析 business_context.md             │
├─────────────────────────────────────────────────────────────┤
│  rules/engine.py    →  规则引擎（确定性检测）                 │
│  ├─ outdated_checker.py   KB vs 规则（数值/布尔/枚举对比）    │
│  ├─ empty_checker.py      空答案 + 过短检测                  │
│  ├─ duplicate_checker.py  精确重复 + Jaccard 模糊匹配        │
│  └─ contradiction_checker.py  同类别断言对比                  │
├─────────────────────────────────────────────────────────────┤
│  llm/                →  LLM 语义检测（Mock / DeepSeek API）  │
│  ├─ mock_detector.py   预设结果（开发/测试用）               │
│  └─ real_detector.py   DeepSeek API 调用                    │
├─────────────────────────────────────────────────────────────┤
│  governance/advisor.py  →  合并结果 + 去重 + 定优先级        │
│  reporter/               →  JSON + Markdown 双报告           │
└─────────────────────────────────────────────────────────────┘
```

### 规则引擎检测逻辑

#### 1. 内容过时检测（`outdated_checker.py`）

- 将 `business_context.md` 中的业务规则解析为结构化数据（数值/布尔/枚举）
- 从 KB 条目中提取关键信息与规则进行结构化对比
- **数值级差** → `outdated`（如 48h vs 24h）
- **布尔相反** → `contradictory_business`（如"支持货到付款" vs "不支持"）
- **枚举不符** → `outdated`（如"顺丰" vs "中通/韵达/圆通"）

#### 2. 空答案检测（`empty_checker.py`）

- `answer` 为空 → `empty_answer`
- `len(answer) < 10` 字符 → `incomplete`

#### 3. 重复检测（`duplicate_checker.py`）

- 精确重复：`question` 字段完全一致
- 模糊重复：Jaccard 相似度 > 0.8
- 重复 + 答案不同 → 同时标记 `contradictory_internal`

#### 4. 条目间矛盾检测（`contradiction_checker.py`）

- 按 `category` 分组，同组条目两两对比
- 提取关键断言（运费承担方、退货天数等）检测冲突

### LLM 检测逻辑

- **语义矛盾检测**：分析条目间是否存在语义层面的不一致
- **专业度评估**：检测语气推诿、措辞不当等问题
- **改进建议生成**：针对问题条目生成具体的修改建议

---

## 治理建议逻辑

### 问题类型 → 治理动作

| 问题类型 | 建议动作 | 优先级 | 说明 |
|---------|---------|--------|------|
| `contradictory_business` | **update** | **P0** | 立即修复，以业务规则为准重写 |
| `empty_answer` | **create** | **P0** | 立即补充完整答案 |
| `outdated` | **update** | **P1** | 尽快更新数值/描述 |
| `contradictory_internal` | **update** + **merge** | **P1** | 统一说法，保留正确版本 |
| `duplicate` | **merge** | **P1** | 保留最新版本，删除重复 |
| `unprofessional` | **improve** | **P2** | 重写为专业表达 |
| `missing_coverage` | **create** | **P2** | 新增条目覆盖盲区 |
| `incomplete` | **update** | **P2** | 补充缺失信息 |

### 优先级说明

| 优先级 | 对应 Tier | 建议响应时间 | 说明 |
|--------|----------|-------------|------|
| **P0** | Tier 1（关键内容） | 24 小时内 | 与业务规则直接矛盾或空条目 |
| **P1** | Tier 2（高流量内容） | 1 周内 | 内容过时或内部矛盾 |
| **P2** | Tier 3（辅助内容） | 下个迭代周期 | 表达优化或覆盖补充 |

### 质量维度评分（对齐 DAMA-DMBOK 标准）

除问题分类外，工具还从 **6 个质量维度** 定量评估知识库健康状况。

**评分方法**：DAMA-DMBOK 1-5 分制，等权重简单平均

| 分数 | 等级 | 含义 |
|------|------|------|
| 5 | 优秀 | 无条目受影响 |
| 4 | 良好 | ≤10% 条目受影响 |
| 3 | 一般 | 10%~25% 条目受影响 |
| 2 | 待改善 | 25%~50% 条目受影响 |
| 1 | 不合格 | >50% 条目受影响 |

| 维度 | 对应问题类型 | 参考标准 |
|------|-------------|---------|
| **准确性** | 与业务规则矛盾 | DAMA-DMBOK Accuracy / ISO 8000-130 |
| **完整性** | 空答案、回答不完整、覆盖缺失 | DAMA-DMBOK Completeness / KCS 内容检查清单 |
| **一致性** | 条目间矛盾 | DAMA-DMBOK Consistency / ISO 8000-140 |
| **时效性** | 内容过时 | DAMA-DMBOK Timeliness / Atlan Freshness |
| **唯一性** | 重复条目 | DAMA-DMBOK Uniqueness / KCS 唯一性检查 |
| **规范性** | 表达不专业 | DAMA-DMBOK Validity / KCS 内容标准 |

**CQS（综合质量得分）** = 6 项维度得分的简单平均（等权重各 1/6）
**健康率** = 完全无问题条目数 / 总条目数（零缺陷占比）

### 治理动作的权威参考

| 建议操作 | 参考框架 | 说明 |
|---------|---------|------|
| **update**（修改） | ISO 8000-61 纠正措施 | 在数据源头修复，消除根本原因 |
| **merge**（合并） | DAMA-DMBOK 重复数据治理 | 保留权威版本，去除冗余 |
| **delete**（删除） | ISO 8000-61 废弃流程 | 标记并移除失效数据 |
| **create**（新增） | KCS 内容创建标准 | 确保新条目完整、清晰、唯一 |
| **improve**（优化） | TDQM 持续改进循环 | Define→Measure→Analyze→Improve |

---

## 运行说明

### 环境要求

- Python 3.9+
- pip

### 安装

```bash
pip install -r requirements.txt
```

### 配置

编辑项目根目录下的 `config.yaml` 文件：

```yaml
# 切换检测模式
llm_mode: mock          # mock(模拟) | real(真实API)

# real 模式时填写 API Key
deepseek:
  api_key: ""           # 替换为你的 DeepSeek API Key
  model: deepseek-chat
```

### Mock 模式（无需 API Key）

```bash
python main.py --mode mock
```

### 真实 API 模式（使用 DeepSeek）

```bash
# 方式一：修改 config.yaml 中的 api_key
# 方式二：命令行传入
python main.py --mode real --api-key sk-your-deepseek-api-key
```

### 选项

```bash
# 指定输出目录
python main.py --mode mock --output-dir ./my_output

# 指定数据文件路径
python main.py --mode mock --kb-file ./data/kb.json --business-context ./data/rules.md
```

### 输出

| 文件 | 说明 |
|------|------|
| `output/report.json` | 结构化数据报告（含完整分析数据） |
| `output/report.md` | 面向业务方的可读治理报告 |

---

## AI 工具使用情况

### 开发阶段使用的 AI 工具

本项目使用 **Claude Code**（Anthropic 的 AI 编程助手）辅助开发：

| 用途 | 说明 |
|------|------|
| **方案设计** | Claude Code 帮助设计了整体架构和问题分类体系，并调研了国际权威框架 |
| **代码生成** | Claude Code 自动生成了全部模块的代码（规则引擎、LLM 检测器、报告生成器等） |
| **调试修复** | Claude Code 发现了 Python 3.9 类型语法兼容问题并进行了修复 |
| **误报修复** | Claude Code 识别并修复了过时检测器中的逻辑误报 |

### 检测工具自身的 AI 使用

本工具在 **LLM 检测模块** 中可选择使用大语言模型：

| 项目 | 说明 |
|------|------|
| **使用场景** | 语义矛盾检测、专业度评估、改进建议生成 |
| **支持模型** | DeepSeek（通过 OpenAI 兼容 API 调用） |
| **调用方式** | 仅通过 API 调用，不传输敏感数据 |
| **安全声明** | 检测报告包含 LLM 生成的内容，使用前请人工复核 |

---

## 检测结果摘要

对提供的 40 条样本数据进行检测，结果如下：

| 指标 | 数值 |
|------|------|
| 总条目数 | 40 |
| 问题条目数 | 15 |
| 健康率（零缺陷占比） | 62.5% |
| 综合质量得分（CQS） | **3.8 / 5.0（B级良好）** |
| 总问题数 | 17 |
| P0（立即处理） | 3 |
| P1（尽快处理） | 11 |
| P2（常规优化） | 1 |

### 各维度评分（DAMA-DMBOK 1-5分制）

| 维度 | 评分 | 等级 | 说明 |
|------|------|------|------|
| 准确性 | 4/5 | 良好 | 仅 2.5% 条目受影响（1条与业务规则矛盾） |
| 完整性 | 4/5 | 良好 | 7.5% 条目受影响（空答案/覆盖缺失） |
| 一致性 | 4/5 | 良好 | 10% 条目存在内部矛盾 |
| 时效性 | **3/5** | **一般** ⚠️ | 17.5% 条目信息过时（需重点治理） |
| 唯一性 | 4/5 | 良好 | 2.5% 条目存在重复 |
| 规范性 | 4/5 | 良好 | 2.5% 条目表达不专业 |

### 问题类型分布

| 问题类型 | 数量 |
|---------|------|
| 内容过时 | 7 |
| 条目间矛盾 | 4 |
| 空答案 | 2 |
| 重复条目 | 1 |
| 与业务规则矛盾 | 1 |
| 覆盖缺失 | 1 |
| 表达不专业 | 1 |

### 各类别健康状况

| 分类 | 健康率 |
|------|-------|
| 退货政策 | 44.4% |
| 物流 | 50.0% |
| 发票 | 0.0% |
| 会员 | 66.7% |
| 优惠 | 75.0% |
| 客服 | 66.7% |
| 支付 | 75.0% |
| 售后 | 50.0% |
| 账号 | 50.0% |

### 治理建议汇总

| 操作类型 | 数量 |
|---------|------|
| 修改（update） | 12 条 |
| 合并（merge） | 1 组 |
| 新增（create） | 2 条 |
| 优化（improve） | 1 条 |

---

## 项目结构

```
├── main.py                 # CLI 入口
├── config.yaml              # YAML 配置文件
├── config.yaml              # YAML 配置文件
├── README.md               # 项目文档
├── requirements.txt        # Python 依赖
│
├── config/
│   └── settings.py         # 全局配置
│
├── data/
│   ├── models.py           # 数据模型
│   └── loader.py           # 数据加载器
│
├── rules/
│   ├── parser.py           # 业务规则解析
│   ├── engine.py           # 规则引擎调度器
│   ├── outdated_checker.py # 过时检测
│   ├── empty_checker.py    # 空答案检测
│   ├── duplicate_checker.py# 重复检测
│   └── contradiction_checker.py # 矛盾检测
│
├── llm/
│   ├── base.py             # LLM 抽象接口
│   ├── mock_detector.py    # Mock 模式
│   ├── real_detector.py    # DeepSeek API
│   └── prompts.py          # Prompt 模板
│
├── governance/
│   ├── advisor.py          # 治理建议生成器
│   └── priorities.py       # 优先级排序
│
├── reporter/
│   ├── json_reporter.py    # JSON 报告
│   └── markdown_reporter.py# Markdown 报告
│
├── output/                 # 报告输出目录
│   ├── report.json
│   └── report.md
│
└── tests/                  # 单元测试
```
