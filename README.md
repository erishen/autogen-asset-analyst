# AutoGen Asset Analyst - Investment Research Roundtable

[中文文档](README.zh-CN.md)

Multiple AutoGen agents with different investment perspectives **debate** and reach **consensus** on portfolio decisions. Unlike a deterministic pipeline, this project leverages AutoGen's conversational multi-agent strength.

## Features

- 🏦 **Multi-Agent Debate**: 4 agents (Value, Technical, Risk, Director) debate investment decisions
- 📚 **Personal Knowledge Integration**: Retrieves user's investment preferences and strategy from langchain-llm-toolkit RAG
- 📈 **Market Trend Analysis**: Extracts recent index trends (SSE, CSI300, Nasdaq, Gold, Fed rate) for forward-looking analysis
- 💱 **Currency-Aware**: Automatically detects USD/HKD products and shows CNY equivalent
- 📝 **Transaction Tracking**: Reads recent buy/sell records to factor in trading patterns
- 🇨🇳 **Domestic Rate Context**: Includes Chinese deposit rate, LPR, and bond yields for local context
- 🛡️ **Risk Veto**: Risk Controller can veto any dangerous recommendation
- 📊 **Compact Output**: Concise final report with market judgment, action items, and risk warnings

## Architecture

```
                    ┌─────────────────────┐
                    │   asset-lens Data   │
                    │ (calculate/analyze) │
                    └──────────┬──────────┘
                               │
          ┌────────────────────┼────────────────────┐
          │                    │                    │
 ┌────────▼────────┐ ┌────────▼────────┐ ┌────────▼────────┐
 │ Market Snapshot │ │   Transactions  │ │ Knowledge Base  │
 │ (index trends,  │ │ (recent 60 days │ │ (personal invest│
 │  rate context)  │ │  buy/sell recs) │ │  preferences)   │
 └────────┬────────┘ └────────┬────────┘ └────────┬────────┘
          │                    │                    │
          └────────────────────┼────────────────────┘
                               │
                    ┌──────────▼──────────┐
                    │   DataCollector      │
                    │ (reads JSON + CSV)   │
                    └──────────┬──────────┘
                               │
          ┌────────────────────┼────────────────────┐
          │                    │                    │
 ┌────────▼────────┐ ┌────────▼────────┐ ┌────────▼────────┐
 │ 🏦 Value        │ │ 📈 Technical    │ │ 🛡️ Risk         │
 │   Investor      │ │   Analyst       │ │   Controller    │
 │   (brief)       │ │   (brief)       │ │   (VETO, brief) │
 └────────┬────────┘ └────────┬────────┘ └────────┬────────┘
          │                    │                    │
          │        SelectorGroupChat               │
          │          (Compact Debate)               │
          │                    │                    │
          └────────────────────┼────────────────────┘
                               │
                    ┌──────────▼──────────┐
                    │ 👔 Investment       │
                    │   Director          │
                    │ (Final Decision     │
                    │  Market Judgment +  │
                    │  Action Items +     │
                    │  Risk Warnings)     │
                    └──────────┬──────────┘
                               │
                    ┌──────────▼──────────┐
                    │   HTML Report       │
                    └─────────────────────┘
```

### Agents

| Agent | Role | Output |
|-------|------|--------|
| **ValueInvestorAgent** 🏦 | Fundamentals & long-term value | 3-5 sentences, specific products |
| **TechnicalAnalystAgent** 📈 | Trend & momentum signals | 3-5 sentences, trend judgment |
| **RiskControllerAgent** 🛡️ | Risk concentration & veto | 2-3 sentences, veto if needed |
| **InvestmentDirectorAgent** 👔 | Synthesizes final decision | Market judgment + actions + risks |

### Analysis Pipeline

1. **asset-lens** generates portfolio data via `make calculate`, `make analyze`
2. **Market Snapshot**: Reads recent 4 weeks of index data (上证, 沪深300, 纳指100, 黄金, 利率)
3. **Transaction Records**: Extracts recent 60-day buy/sell activity from product CSV
4. **Knowledge Base**: Queries langchain-llm-toolkit RAG for personal investment preferences
5. **DataCollector** aggregates everything with currency and annualized-return context
6. **Agents debate** with concise inputs, Investment Director produces final decision
7. **HTML Report** generated with compact summary

## Data Sources

### Portfolio Data (asset-lens)
The project reads data from [asset-lens](../asset-lens/) via JSON output (`投资收益率分析_YYYYMMDD.json`).

### Personal Knowledge (langchain-llm-toolkit)
Retrieves investment preferences and methodology from the RAG vector store configured via `KNOWLEDGE_BASE_PATH`. The knowledge base should contain investment-related documents only (methodology, financial planning, strategy).

### Market Data (CSV)
Reads `资产汇总-表格 1.csv` for index trends and `投资产品-表格 1.csv` for transaction records from ts-demo data directory.

## Project Structure

```
autogen-asset-analyst/
├── src/autogen_asset_analyst/
│   ├── __init__.py              # Package init with version
│   ├── agents.py                # 4 AutoGen agent definitions (compact prompts)
│   ├── config.py                # Pydantic settings from .env
│   ├── analyzer.py              # Roundtable orchestration
│   ├── data_collector.py        # Data collection (JSON + CSV + rates)
│   ├── knowledge_retriever.py   # RAG knowledge base integration
│   ├── visualization.py         # HTML report generation
│   └── cli.py                   # Typer CLI entry point
├── tests/
│   ├── __init__.py
│   ├── test_analyzer.py         # Tests for _build_initial_message
│   └── test_knowledge_retriever.py  # Tests for knowledge retrieval
├── output/                      # Generated HTML reports
├── .env
├── .env.example
├── pyproject.toml
├── README.md
└── README.zh-CN.md
```

## Quick Start

### 1. Install Dependencies

```bash
cd invest-kit/apps/autogen-asset-analyst
uv sync
```

### 2. Configure Environment

```bash
cp .env.example .env
# Edit .env:
#   OPENAI_API_KEY=your_key
#   OPENAI_BASE_URL=https://api.deepseek.com
#   ASSET_LENS_PATH=../asset-lens
#   KNOWLEDGE_BASE_PATH=../langchain-llm-toolkit
```

### 3. Prepare Data

```bash
# Ensure latest data is generated
cd ../asset-lens
make calculate
make analyze
```

### 4. Run Analysis

```bash
# Full analysis with report
uv run autogen-analyst report --date 20260619 --output ./output

# Roundtable discussion only
uv run autogen-analyst roundtable --date 20260619

# Show version
uv run autogen-analyst version
```

### 5. Run Tests

```bash
uv run pytest tests/ -v
```

Output: `20 passed`

## Configuration

| Variable | Default | Description |
|----------|---------|-------------|
| `DEFAULT_MODEL` | `deepseek-chat` | LLM model name |
| `OPENAI_API_KEY` | - | OpenAI-compatible API key |
| `OPENAI_BASE_URL` | `https://api.deepseek.com` | API base URL |
| `ASSET_LENS_PATH` | `../asset-lens` | Path to asset-lens project |
| `KNOWLEDGE_BASE_PATH` | `../langchain-llm-toolkit` | Path to RAG knowledge base |
| `ROUNDTABLE_MAX_ROUNDS` | `6` | Maximum discussion rounds |
| `API_HOST` | `0.0.0.0` | API server host |
| `API_PORT` | `8002` | API server port |

## Output Format

The Investment Director produces a compact final report:

```
## 📊 Market Judgment
  - Next week direction (one sentence)
  - Key drivers (rates, policy, index trends)

## 📈 Action Items
  - Add positions (product + amount + reason)
  - Reduce/redeem (product + amount + reason)
  - Hold & watch (product + reason)

## ⚠️ Risk Warnings
```

## License

MIT
