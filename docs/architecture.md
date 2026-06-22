# autogen-asset-analyst 架构文档

## 概述

autogen-asset-analyst 是一个基于 AutoGen 多智能体框架的投资研究圆桌分析系统。四个 AI 分析师（价值投资、技术分析、风险控制、投资总监）围绕投资组合数据进行多轮辩论，最终产出结构化的调仓建议。

**核心理念**：不是直接问 LLM "该怎么调仓"，而是让同一个 LLM 扮演 4 个立场互斥的角色互相辩论，逼迫它从多个维度审视投资组合，减少单一视角的盲区。

## 架构总览

```
                    ┌──────────────────────────────────┐
                    │        data_collector.py          │
                    │                                    │
  asset-lens JSON ──┤  format_portfolio_context()       │
  market CSV ───────┤  extract_market_snapshot()        ├──→ 文本上下文
  transaction CSV ──┤  extract_recent_transactions()    │
                    └──────────────────────────────────┘
                                                        │
  RAG 知识库 ──────→ knowledge_retriever.py ────────────┤
  (FAISS 本地)        retrieve_personal_knowledge()     │
                                                        ↓
                    ┌──────────────────────────────────┐
                    │        analyzer.py                │
                    │    _build_initial_message()        │
                    │                                    │
                    │  portfolio + market + tx +        │
                    │  knowledge + instructions         │
                    └──────────────┬───────────────────┘
                                   │ 初始消息
                    ┌──────────────▼───────────────────┐
                    │     SelectorGroupChat (AutoGen)     │
                    │     LLM 动态决定发言顺序              │
                    │                                    │
                    │  ┌──────────┐  ┌──────────┐       │
                    │  │价值分析师 │  │技术分析师 │       │
                    │  └──────────┘  └──────────┘       │
                    │  ┌──────────┐  ┌──────────┐       │
                    │  │ 风控官   │  │投资总监  │       │
                    │  └──────────┘  └──────────┘       │
                    │                                    │
                    │  多轮辩论 → 共识决策               │
                    └──────────────┬───────────────────┘
                                   │ 对话记录 + 共识
                    ┌──────────────▼───────────────────┐
                    │     visualization.py              │
                    │     生成 HTML 报告                 │
                    └──────────────────────────────────┘
```

## 数据流详解

系统启动后按 6 步流水线执行：

```
Step 1: 数据收集  ── 读取 asset-lens 输出的投资收益率分析 JSON
Step 2: 市场快照  ── 读取资产汇总 CSV，计算近4周指数涨跌趋势
Step 3: 交易记录  ── 读取投资产品 CSV，提取近60天买入/卖出记录
Step 4: 知识检索  ── 查询 RAG 向量库，获取个人投资偏好和经验
Step 5: 消息组装  ── 以上四类数据拼接为初始消息文本
Step 6: 圆桌辩论  ── AutoGen SelectorGroupChat 多轮讨论
Step 7: 报告输出  ── 提取共识+否决记录，生成 HTML
```

### 初始消息结构

所有数据蒸馏为一段文本注入 Agent：

```
各位分析师，欢迎参加今天的投资研究圆桌会议。

⚠️ 分析注意事项：
1. 部分产品为美元/港元计价，评估时请换算为人民币
2. 年化收益率不等于实际收益率——短期产品的实际亏损远小于年化值
3. 当前存款基准利率仅 <CN_DEPOSIT_RATE>%，判断低效产品时应以此为准

=== 投资组合概览 ===
总产品数: <N>, 总资产: <总资产>元
有效投资收益率: <收益率>%

=== 汇率信息 ===
美元: <汇率> CNY/USD, 港元: <汇率> CNY/HKD

=== 收益率排名前10 ===
1. <产品A>: 年化<X>%, <金额>, 持有<Y>天
...

=== 近期市场趋势（4周） ===
上证: <前值> → <后值> (↑/↓<X>%)
沪深300: ...
纳指100: ...
黄金GLD: ...

=== 国内利率环境 ===
存款基准利率: <CN_DEPOSIT_RATE>%, 1年期LPR: <CN_LPR_RATE>%

=== 近期交易记录（60天） ===
<日期>: <买入/卖出>「<产品名称>」<金额>元
...

=== 个人投资知识 ===
投资偏好：<从 RAG 检索到的偏好摘要>
投资经验：<从 RAG 检索到的经验摘要>
财务目标：<从 RAG 检索到的目标摘要>

请各位从自己的专业角度分析讨论。必须产出：
1. Top 5 值得加仓的产品 + 理由 + 预期收益
2. Top 5 需要减仓的产品 + 止损原因
3. 下周具体调仓建议（产品+操作+金额区间+执行时机）
4. 优先级排序
```

## 智能体定义

四个 Agent 本质上都是同一个 DeepSeek API，通过不同的 system prompt 扮演不同角色。

### ValueInvestorAgent（价值投资分析师）

核心理念：
- 寻找内在价值被低估的优质资产
- 长期持有优质产品，忽略短期市场噪音
- 稳定的年化收益率比短期暴利更重要
- 低风险产品（债券、货币基金）是组合的压舱石
- 对于短期波动导致收益下降的产品，应保持耐心

立场：支持长期定投和低风险配置，反对频繁调仓和追逐高收益。

### TechnicalAnalystAgent（技术分析师）

核心理念：
- 趋势是朋友，顺势而为比逆势操作更明智
- 收益率持续上升的产品值得加仓，持续下降的应考虑减仓
- 止盈止损是纪律，不是选择
- 短期观察（7天、30天）的收益变化比长期平均更有参考价值

立场：支持加仓强势产品和止盈止损，反对长期持有持续走弱的产品。

### RiskControllerAgent（风险控制官）

拥有一票否决权。核心风险标准：
- 单一产品占比 > 20%：高风险
- 单一类型占比 > 40%：集中度风险
- 高风险产品占比 > 50%：组合风险过高
- 行使否决权时使用【否决】标记

### InvestmentDirectorAgent（投资总监）

主持圆桌，综合各方意见形成共识。最终发言格式：
```
## 一、市场判断
## 二、操作建议（加仓 / 减仓 / 持有 + 金额区间 + 理由）
## 三、下周行动项（按优先级排序）
## 四、风险警告

以 ROUNDTABLE_COMPLETE 结束。
```

## 消息格式：AutoGen → OpenAI API

底层是标准的 **OpenAI Chat Completions API** 格式。源码 `autogen_ext/models/openai/_message_transform.py` 中的映射：

```
AutoGen 内部类型               →  OpenAI API
────────────────────────────────────────────────
SystemMessage(content=风控规则)  →  {"role": "system", "content": "风控规则"}
UserMessage(source="user",      →  {"role": "user", "name": "user", "content": "..."}
             content=投资数据)
AssistantMessage(source=风控官,  →  {"role": "assistant", "content": "【否决】..."}
                  content=否决)
```

### 第 1 次 API 调用（风控官发言）

```json
{
  "model": "deepseek-chat",
  "messages": [
    {"role": "system", "content": "你是投资组合的风险控制官..."},
    {"role": "user", "name": "user", "content": "投资组合数据 + 市场趋势 + 交易记录 + 个人知识..."}
  ]
}
```

### 第 2 次 API 调用（技术派发言）

```json
{
  "model": "deepseek-chat",
  "messages": [
    {"role": "system", "content": "你是技术分析师..."},
    {"role": "user", "name": "user", "content": "投资组合数据..."},
    {"role": "assistant", "content": "【否决】某某建议因风险过高被否决..."}
  ]
}
```

### 第 3 次 API 调用（总监总结）

```json
{
  "model": "deepseek-chat",
  "messages": [
    {"role": "system", "content": "你是投资总监..."},
    {"role": "user", "name": "user", "content": "投资组合数据..."},
    {"role": "assistant", "content": "【否决】..."},
    {"role": "assistant", "content": "趋势判断：加仓XX，止损YY..."}
  ]
}
```

**关键点**：
- 每次只换 `system` prompt，完整对话历史累积追加
- `UserMessage` 带 `name` 字段（agent 名），`AssistantMessage` 不带
- 对 DeepSeek 来说就是同一个 API 的多次请求，不是多个模型

## 数据收集模块 (data_collector.py)

### 四个数据源

| 数据 | 来源 | 函数 | 频率 |
|------|------|------|------|
| 投资组合 | `asset-lens/output/投资收益率分析_{date}.json` | `collect_analysis_data()` | 每次分析 |
| 市场趋势 | CSV `资产汇总-表格 1.csv` | `extract_market_snapshot()` | 每次分析 |
| 交易记录 | CSV `投资产品-表格 1.csv` | `extract_recent_transactions()` | 每次分析 |
| 个人知识 | langchain-llm-toolkit RAG 向量库 | `retrieve_personal_knowledge()` | 每次分析 |

### 关键格式化逻辑

- **货币区分**：美元产品自动标注 `$` 并换算 CNY
- **年化vs实际**：亏损产品附注实际盈亏和持有天数，避免年化误导
- **低效判断**：以配置的存款利率为基准（`.env` 中 `CN_DEPOSIT_RATE`）
- **市场趋势**：从 CSV 取最近 4 行计算指数涨跌百分比
- **交易记录**：读取 CSV 中总买入/总卖出非零的产品

## 配置

### .env 文件

```bash
# LLM
OPENAI_API_KEY=sk-xxx
OPENAI_BASE_URL=https://api.deepseek.com/v1
DEFAULT_MODEL=deepseek-chat

# 数据路径
ASSET_LENS_PATH=../asset-lens
KNOWLEDGE_BASE_PATH=../langchain-llm-toolkit

# 国内利率（如需调整直接改这里）
CN_DEPOSIT_RATE=1.45
CN_LPR_RATE=3.1
CN_BOND_YIELD=1.7

# 行为控制
ROUNDTABLE_MAX_ROUNDS=6
```

## 知识检索模块 (knowledge_retriever.py)

在分析前，从 langchain-llm-toolkit 的本地 RAG 向量库检索个人投资知识：

```python
queries = [
    "投资偏好 策略 长期目标 收益预期",
    "投资经验 资产配置 教训 调仓习惯",
    "财务目标 年化收益 风险承受",
]
for query in queries:
    docs = rag.retrieve_hybrid(query, k=3, bm25_weight=0.3)
    # 30% BM25关键词 + 70% 语义向量混合搜索
```

检索结果格式化后注入初始消息，Agent 在讨论时会参考投资人的实际投资风格。

**隐私设计**：所有知识库数据（Markdown 源文档 + FAISS 向量索引）完全本地存储，嵌入使用本地 Ollama 模型（`nomic-embed-text`），不依赖外部 API。

## 使用方法

### 前置条件

```bash
# 1. 先运行 asset-lens 生成最新数据
cd ../asset-lens && make calculate && make analyze

# 2. 确保 RAG 向量库已构建
cd ../langchain-llm-toolkit
# 导入知识文档后，向量库在 vector_store/ 下

# 3. 确保 Ollama 在运行（用于嵌入）
ollama serve
```

### 命令行

```bash
# 生成指定日期的分析报告
uv run autogen-analyst report --date 20260619 --output ./output

# 先生成对话记录再生成报告（两步）
uv run autogen-analyst roundtable --date 20260619
uv run autogen-analyst report --date 20260619 --output ./output
```

### Python API

```python
import asyncio
from autogen_asset_analyst.analyzer import run_roundtable_async

result = await run_roundtable_async(
    asset_lens_path="../asset-lens",
    max_rounds=4,
    date="20260619",
)

print(f"共识: {result.consensus}")
print(f"否决: {result.vetoes}")
print(f"Token: {result.token_usage}")
```

### 输出

生成 HTML 报告到 `output/roundtable_report_{timestamp}.html`，包含：
- 讨论摘要（轮数、消息数、Token 用量）
- 完整对话记录（Agent 发言卡片）
- 否决记录
- 投资总监最终共识（结构化建议：市场判断 + 操作建议 + 行动项 + 风险警告）

## 设计决策

### 为什么用 AutoGen 而不是直接 Prompt？

单次问 LLM "怎么调仓"得到单一角度。4 个角色辩论能从价值/趋势/风控三个维度审视组合，减少盲区。

### 为什么全部数据蒸馏成文本？

**简单性优先**。JSON/CSV/向量结果统一格式化为文本，Agent 无需解析结构化数据。代价是 Token 消耗较大（18K-43K），但避免了复杂的 Agent 间数据传递协议。

### 为什么用本地嵌入？

RAG 向量化使用 Ollama 本地模型，所有投资知识完全本地存储，不依赖外部 API，保护隐私。

### 局限

1. **同一 LLM，不同人格**：四个 Agent 共享同一个 DeepSeek 模型，人格差异仅来自 system prompt
2. **无工具调用**：Agent 不能主动查数据——所有数据在初始消息中一次性提供
3. **依赖数据质量**：分析质量完全取决于 asset-lens 和 CSV 数据的准确性和完整性
4. **Token 消耗大**：全量上下文注入 + 多轮对话，单次分析 18K-43K tokens
5. **辩论未必收敛**：如果角色设定不够尖锐，可能出现"大家都同意"的情况

## 项目结构

```
autogen-asset-analyst/
├── src/autogen_asset_analyst/
│   ├── agents.py              # Agent 定义（4个角色 + system prompt）
│   ├── analyzer.py            # 核心编排（数据流 + 圆桌 + 共识提取）
│   ├── cli.py                 # 命令行接口
│   ├── config.py              # Pydantic 配置（从 .env 读取）
│   ├── data_collector.py      # 数据收集（组合 + 市场 + 交易 + 利率）
│   ├── knowledge_retriever.py # RAG 知识检索
│   ├── visualization.py       # HTML 报告生成
│   └── __init__.py
├── tests/
│   ├── test_analyzer.py
│   ├── test_knowledge_retriever.py
│   └── ...
├── .env                       # 环境配置
├── .env.example               # 配置模板
├── pyproject.toml
├── README.md
├── README.zh-CN.md
└── docs/
    └── architecture.md        # 本文档
```
