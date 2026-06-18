# AutoGen 资产分析师 - 投资研究圆桌会议

[English](README.md)

多个 AutoGen 智能体从不同投资视角**辩论**并**达成共识**，做出投资组合决策。与确定性流水线不同，本项目充分利用 AutoGen 的对话式多智能体优势。

## 架构

```
                    ┌─────────────────────┐
                    │   asset-lens 数据   │
                    │ (calculate/analyze) │
                    └──────────┬──────────┘
                               │
                    ┌──────────▼──────────┐
                    │   数据收集器         │
                    │ (读取 JSON 输出)     │
                    └──────────┬──────────┘
                               │
          ┌────────────────────┼────────────────────┐
          │                    │                    │
 ┌────────▼────────┐ ┌────────▼────────┐ ┌────────▼────────┐
 │ 🏦 价值投资     │ │ 📈 技术分析师   │ │ 🛡️ 风险控制官   │
 │   分析师        │ │                 │ │   (一票否决权)   │
 └────────┬────────┘ └────────┬────────┘ └────────┬────────┘
          │                    │                    │
          │        RoundRobinGroupChat              │
          │          (辩论 & 讨论)                  │
          │                    │                    │
          └────────────────────┼────────────────────┘
                               │
                    ┌──────────▼──────────┐
                    │ 👔 投资总监         │
                    │   (主持讨论 &       │
                    │    综合共识)        │
                    └──────────┬──────────┘
                               │
                    ┌──────────▼──────────┐
                    │   HTML 报告         │
                    │ (辩论记录 +         │
                    │  共识决策 +         │
                    │  风险警告)          │
                    └─────────────────────┘
```

### 智能体

| 智能体 | 角色 | 核心特征 |
|--------|------|----------|
| **ValueInvestorAgent** 🏦 | 从基本面和长期价值角度评估 | 耐心对待波动，持有优质产品 |
| **TechnicalAnalystAgent** 📈 | 从趋势和动量角度评估 | 顺势而为，止盈止损 |
| **RiskControllerAgent** 🛡️ | 风险控制，拥有一票否决权 | 可以否决任何危险建议 |
| **InvestmentDirectorAgent** 👔 | 主持讨论，综合共识 | 决定何时达成最终结论 |

### 与 langgraph-csv-analyst 的关键区别

| 特性 | langgraph-csv-analyst | autogen-asset-analyst |
|------|----------------------|----------------------|
| 模式 | 确定性流水线 | 对话式辩论 |
| 智能体交互 | 顺序传递 | 轮流讨论 |
| 决策方式 | 最后一个智能体决定 | 通过辩论达成共识 |
| 风险控制 | 仅评估 | 一票否决权 |
| 数据源 | CSV 文件 | asset-lens JSON 输出 |
| 输出 | 分析报告 | 辩论记录 + 共识决策 |

### 对话流程

1. **数据收集器** 从 asset-lens 收集投资组合数据（读取 `投资收益率分析_YYYYMMDD.json`）
2. **投资总监** 以投资组合概要开始讨论
3. 每个智能体轮流提供自己的观点
4. 智能体**辩论**具体产品和策略
5. **风险控制官**可以否决危险的建议（【否决】）
6. **投资总监**综合各方意见形成共识决策
7. 生成 HTML 报告，包含讨论记录、共识决策和 Token 用量

## 数据源

项目通过以下方式从 [asset-lens](../asset-lens/) 读取数据：

1. `make calculate` - 通过 `CalculateReportGenerator` 类
2. `make analyze` - 读取 `output/投资收益率分析_YYYYMMDD.json`
3. `make compare` - 可选的趋势数据

最丰富的数据来自 `analyze` 的 JSON 输出，包含：
- `portfolio_summary`（总价值、总利润、收益率）
- `top_performers`、`low_returns`、`short_term_observation`
- `type_distribution`、`risk_distribution`
- `time_group_analysis`
- `comprehensive_evaluation`
- `optimization_suggestions`、`investment_advice`
- `products`（所有产品详情）

## 项目结构

```
autogen-asset-analyst/
├── src/autogen_asset_analyst/
│   ├── __init__.py          # 包初始化及版本
│   ├── agents.py            # 4个 AutoGen 智能体定义
│   ├── config.py            # Pydantic 配置（从 .env 加载）
│   ├── analyzer.py          # 圆桌会议编排
│   ├── data_collector.py    # 从 asset-lens 收集数据
│   ├── visualization.py     # HTML 报告（含辩论记录）
│   └── cli.py               # Typer 命令行工具
├── .env.example
├── pyproject.toml
├── README.md
└── README.zh-CN.md
```

## 快速开始

### 1. 安装依赖

```bash
cd invest-kit/apps/autogen-asset-analyst
uv sync
```

### 2. 配置环境

```bash
cp .env.example .env
# 编辑 .env 文件，设置你的 OPENAI_API_KEY 和 ASSET_LENS_PATH
```

### 3. 运行圆桌会议

```bash
# 运行完整的圆桌讨论（使用最新分析数据）
uv run autogen-analyst roundtable

# 指定 asset-lens 路径
uv run autogen-analyst roundtable --asset-lens-path ../asset-lens

# 设置最大讨论轮数
uv run autogen-analyst roundtable --max-rounds 4

# 分析指定日期的数据
uv run autogen-analyst roundtable --date 20260613

# 生成 HTML 报告
uv run autogen-analyst report --output ./output

# 生成指定日期的 HTML 报告
uv run autogen-analyst report --date 20260613 --output ./output

# 显示版本
uv run autogen-analyst version
```

每次运行后会输出 Token 用量：
```
Messages: 5 | Vetoes: 1
Tokens: 27111 (prompt: 22155, completion: 4956)
```

## 配置

所有设置通过 pydantic-settings 从 `.env` 文件加载：

| 变量 | 默认值 | 说明 |
|------|--------|------|
| `DEFAULT_MODEL` | `deepseek-chat` | LLM 模型名称 |
| `OPENAI_API_KEY` | - | OpenAI 兼容 API 密钥 |
| `OPENAI_BASE_URL` | `https://api.deepseek.com` | API 基础 URL |
| `ASSET_LENS_PATH` | `../asset-lens` | asset-lens 项目路径 |
| `ROUNDTABLE_MAX_ROUNDS` | `6` | 最大讨论轮数 |
| `API_HOST` | `0.0.0.0` | API 服务主机 |
| `API_PORT` | `8002` | API 服务端口 |

## 许可证

MIT
