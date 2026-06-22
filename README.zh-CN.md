# AutoGen 资产分析师 - 投资研究圆桌会议

[English](README.md)

多个 AutoGen 智能体从不同投资视角**辩论**并**达成共识**，做出投资组合决策。结合个人知识库、市场趋势和交易记录，输出简洁可执行的下周操作建议。

## 功能特性

- 🏦 **多智能体辩论**：4 个 Agent（价值、技术、风控、总监）辩论投资决策
- 📚 **个人知识整合**：从 langchain-llm-toolkit RAG 检索投资偏好和策略
- 📈 **市场趋势分析**：提取近期指数走势（上证、沪深300、纳指、黄金、利率）
- 💱 **货币感知**：自动识别美元/港元产品，标注 CNY 换算
- 📝 **交易记录追踪**：读取最近 60 天买卖记录，分析交易模式
- 🇨🇳 **国内利率环境**：包含存款基准利率、LPR、国债收益率
- 🛡️ **一票否决**：风控官可否决任何高风险建议
- 📊 **精简输出**：只输出最终决策，不展示冗长辩论过程

## 分析流程

1. **asset-lens** 通过 `make calculate`、`make analyze` 生成投资组合数据
2. **市场快照**：读取最近 4 周指数数据（上证、沪深300、纳指100、黄金、利率）
3. **交易记录**：提取最近 60 天产品买卖记录
4. **知识库**：查询 langchain-llm-toolkit RAG 获取个人投资偏好
5. **数据聚合**：DataCollector 汇总所有数据，含货币换算和年化vs实际收益提醒
6. **智能体辩论**：各方简要发言，投资总监产出最终决策
7. **HTML 报告**：生成精简的总结报告

## 数据来源

| 来源 | 内容 |
|------|------|
| asset-lens JSON | 投资组合概览、产品明细、收益率排名 |
| 资产汇总 CSV | 周度市场指数（上证、沪深300、纳指、黄金GLD、利率） |
| 投资产品 CSV | 产品交易记录（买卖时点、金额） |
| langchain-llm-toolkit RAG | 个人投资偏好、方法论、财务规划文档 |

## 项目结构

```
autogen-asset-analyst/
├── src/autogen_asset_analyst/
│   ├── __init__.py              # 包初始化
│   ├── agents.py                # 4 个 Agent 定义（精简提示词）
│   ├── config.py                # Pydantic 配置（从 .env 加载）
│   ├── analyzer.py              # 圆桌讨论编排
│   ├── data_collector.py        # 数据收集（JSON + CSV + 利率）
│   ├── knowledge_retriever.py   # RAG 知识库集成
│   ├── visualization.py         # HTML 报告生成
│   └── cli.py                   # CLI 入口
├── tests/
│   ├── test_analyzer.py         # _build_initial_message 测试
│   └── test_knowledge_retriever.py  # 知识检索测试
├── output/                      # 生成的 HTML 报告
├── .env
├── pyproject.toml
└── README.md
```

## 快速开始

```bash
# 1. 安装依赖
cd invest-kit/apps/autogen-asset-analyst
uv sync

# 2. 配置环境
cp .env.example .env
# 编辑 .env 设置 OPENAI_API_KEY、ASSET_LENS_PATH、KNOWLEDGE_BASE_PATH

# 3. 准备数据
cd ../asset-lens && make calculate && make analyze

# 4. 运行分析
uv run autogen-analyst report --date 20260619 --output ./output

# 5. 运行测试
uv run pytest tests/ -v
```

## 输出格式

投资总监输出精简的最终报告：

```
## 📊 市场判断
  - 下周市场方向
  - 关键驱动因素

## 📈 操作建议
  - 加仓（产品 + 金额 + 原因）
  - 减仓/赎回（产品 + 金额 + 原因）
  - 持有观望（产品 + 原因）

## ⚠️ 风险提示
```

## 配置

| 变量 | 默认值 | 说明 |
|------|--------|------|
| `DEFAULT_MODEL` | `deepseek-chat` | LLM 模型 |
| `OPENAI_API_KEY` | - | API 密钥 |
| `OPENAI_BASE_URL` | `https://api.deepseek.com` | API 地址 |
| `ASSET_LENS_PATH` | `../asset-lens` | asset-lens 路径 |
| `KNOWLEDGE_BASE_PATH` | `../langchain-llm-toolkit` | RAG 知识库路径 |
| `ROUNDTABLE_MAX_ROUNDS` | `6` | 最大讨论轮数 |

## License

MIT
