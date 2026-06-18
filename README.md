# AutoGen Asset Analyst - Investment Research Roundtable

[中文文档](README.zh-CN.md)

Multiple AutoGen agents with different investment perspectives **debate** and reach **consensus** on portfolio decisions. Unlike a deterministic pipeline, this project leverages AutoGen's conversational multi-agent strength.

## Architecture

```
                    ┌─────────────────────┐
                    │   asset-lens Data   │
                    │ (calculate/analyze) │
                    └──────────┬──────────┘
                               │
                    ┌──────────▼──────────┐
                    │   DataCollector      │
                    │ (reads JSON output)  │
                    └──────────┬──────────┘
                               │
          ┌────────────────────┼────────────────────┐
          │                    │                    │
 ┌────────▼────────┐ ┌────────▼────────┐ ┌────────▼────────┐
 │ 🏦 Value        │ │ 📈 Technical    │ │ 🛡️ Risk         │
 │   Investor      │ │   Analyst       │ │   Controller    │
 │                 │ │                 │ │   (VETO power)  │
 └────────┬────────┘ └────────┬────────┘ └────────┬────────┘
          │                    │                    │
          │        SelectorGroupChat               │
          │          (Debate & Discuss)             │
          │                    │                    │
          └────────────────────┼────────────────────┘
                               │
                    ┌──────────▼──────────┐
                    │ 👔 Investment       │
                    │   Director          │
                    │ (Moderates &        │
                    │  Synthesizes        │
                    │  Consensus)         │
                    └──────────┬──────────┘
                               │
                    ┌──────────▼──────────┐
                    │   HTML Report       │
                    │ (Debate Transcript  │
                    │  + Consensus        │
                    │  + Risk Warnings)   │
                    └─────────────────────┘
```

### Agents

| Agent | Role | Key Trait |
|-------|------|-----------|
| **ValueInvestorAgent** 🏦 | Evaluates from fundamentals & long-term value perspective | Patience with dips, holds quality products |
| **TechnicalAnalystAgent** 📈 | Evaluates from trend/momentum perspective | Rides winners, cuts losers |
| **RiskControllerAgent** 🛡️ | One-vote veto on risk issues | Can block any dangerous recommendation |
| **InvestmentDirectorAgent** 👔 | Moderates discussion, synthesizes consensus | Decides when consensus is reached |

### Key Difference from langgraph-csv-analyst

| Feature | langgraph-csv-analyst | autogen-asset-analyst |
|---------|----------------------|----------------------|
| Pattern | Deterministic pipeline | Conversational debate |
| Agent interaction | Sequential pass-through | Round-robin discussion |
| Decision making | Last agent decides | Consensus through debate |
| Risk control | Assessment only | Veto power |
| Data source | CSV file | asset-lens JSON output |
| Output | Analysis report | Debate transcript + consensus |

### Conversation Flow

1. **DataCollector** gathers portfolio data from asset-lens (reads `investment_return_analysis_YYYYMMDD.json`)
2. **InvestmentDirector** starts the discussion with portfolio summary
3. Each agent takes turns providing their perspective
4. Agents **debate** specific products and strategies
5. **RiskController** can veto dangerous recommendations (【否决】)
6. **InvestmentDirector** synthesizes consensus into final decisions
7. Generate HTML report with discussion transcript + consensus + token usage

## Data Source

The project reads data from [asset-lens](../asset-lens/) via:

1. `make calculate` - via `CalculateReportGenerator` class
2. `make analyze` - reads `output/投资收益率分析_YYYYMMDD.json`
3. `make compare` - optional trend data

The richest data is the JSON output from `analyze`, containing:
- `portfolio_summary` (total_value, total_profit, return_rates)
- `top_performers`, `low_returns`, `short_term_observation`
- `type_distribution`, `risk_distribution`
- `time_group_analysis`
- `comprehensive_evaluation`
- `optimization_suggestions`, `investment_advice`
- `products` (all product details)

## Project Structure

```
autogen-asset-analyst/
├── src/autogen_asset_analyst/
│   ├── __init__.py          # Package init with version
│   ├── agents.py            # 4 AutoGen agent definitions
│   ├── config.py            # Pydantic settings from .env
│   ├── analyzer.py          # Roundtable orchestration
│   ├── data_collector.py    # Data collection from asset-lens
│   ├── visualization.py     # HTML report with debate transcript
│   └── cli.py               # Typer CLI entry point
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
# Edit .env and set your OPENAI_API_KEY and ASSET_LENS_PATH
```

### 3. Run Roundtable

```bash
# Run the full roundtable discussion (uses latest analysis data)
uv run autogen-analyst roundtable

# Specify asset-lens path
uv run autogen-analyst roundtable --asset-lens-path ../asset-lens

# Set max discussion rounds
uv run autogen-analyst roundtable --max-rounds 4

# Analyze a specific date's data
uv run autogen-analyst roundtable --date 20260613

# Generate HTML report
uv run autogen-analyst report --output ./output

# Generate report for a specific date
uv run autogen-analyst report --date 20260613 --output ./output

# Show version
uv run autogen-analyst version
```

The CLI outputs token usage after each run:
```
Messages: 5 | Vetoes: 1
Tokens: 27111 (prompt: 22155, completion: 4956)
```

## Configuration

All settings are loaded from `.env` file using pydantic-settings:

| Variable | Default | Description |
|----------|---------|-------------|
| `DEFAULT_MODEL` | `deepseek-chat` | LLM model name |
| `OPENAI_API_KEY` | - | OpenAI-compatible API key |
| `OPENAI_BASE_URL` | `https://api.deepseek.com` | API base URL |
| `ASSET_LENS_PATH` | `../asset-lens` | Path to asset-lens project |
| `ROUNDTABLE_MAX_ROUNDS` | `6` | Maximum discussion rounds |
| `API_HOST` | `0.0.0.0` | API server host |
| `API_PORT` | `8002` | API server port |

## License

MIT
