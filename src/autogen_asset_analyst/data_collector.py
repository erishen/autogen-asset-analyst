"""Data collector for asset-lens analysis data.

Gathers portfolio data from asset-lens by:
1. Running `make calculate` via CalculateReportGenerator
2. Reading the latest `投资收益率分析_*.json` from output
3. Optionally running compare for trend data
"""

from __future__ import annotations

import json
import logging
import subprocess
from pathlib import Path
from typing import Any

from autogen_asset_analyst.config import settings

logger = logging.getLogger(__name__)


class DataCollectorError(Exception):
    """Raised when data collection fails."""


def _find_asset_lens_path(asset_lens_path: str) -> Path:
    """Resolve and validate the asset-lens project path.

    Args:
        asset_lens_path: Path to the asset-lens project directory.

    Returns:
        Resolved Path object.

    Raises:
        DataCollectorError: If the path does not exist.
    """
    path = Path(asset_lens_path).resolve()
    if not path.exists():
        raise DataCollectorError(f"asset-lens path not found: {path}")
    return path


def _find_latest_json(output_dir: Path, pattern: str = "投资收益率分析_*.json", date: str | None = None) -> Path | None:
    """Find the latest JSON file matching the pattern in the output directory.

    Args:
        output_dir: Directory to search in.
        pattern: Glob pattern for the JSON files.
        date: Optional date string (YYYYMMDD) to find a specific file.

    Returns:
        Path to the latest JSON file, or None if not found.
    """
    if not output_dir.exists():
        return None

    if date:
        # Look for a specific date file
        target = output_dir / f"投资收益率分析_{date}.json"
        return target if target.exists() else None

    json_files = sorted(output_dir.glob(pattern), key=lambda p: p.stat().st_mtime, reverse=True)
    return json_files[0] if json_files else None


def collect_analysis_data(asset_lens_path: str, date: str | None = None) -> dict[str, Any]:
    """Read the latest analyze JSON output from asset-lens.

    This is the richest data source, containing:
    - portfolio_summary (total_value, total_profit, return_rates)
    - top_performers, low_returns, short_term_observation
    - type_distribution, risk_distribution
    - time_group_analysis
    - comprehensive_evaluation
    - optimization_suggestions, investment_advice
    - products (all product details)

    Args:
        asset_lens_path: Path to the asset-lens project directory.
        date: Optional date string (YYYYMMDD) to load a specific file.

    Returns:
        A dictionary with the analysis data.

    Raises:
        DataCollectorError: If data cannot be collected.
    """
    path = _find_asset_lens_path(asset_lens_path)
    output_dir = path / "output"

    json_file = _find_latest_json(output_dir, date=date)
    if json_file is None:
        # Try running `make analyze` to generate the JSON
        logger.info("No analysis JSON found, attempting to run `make analyze`...")
        try:
            _run_make_command(path, "analyze")
            json_file = _find_latest_json(output_dir)
        except (subprocess.SubprocessError, FileNotFoundError) as e:
            raise DataCollectorError(
                f"No analysis JSON found in {output_dir} and failed to run `make analyze`: {e}"
            ) from e

    if json_file is None:
        raise DataCollectorError(f"No analysis JSON found in {output_dir} after running `make analyze`")

    try:
        with open(json_file, encoding="utf-8") as f:
            data = json.load(f)
    except (json.JSONDecodeError, OSError) as e:
        raise DataCollectorError(f"Failed to read analysis JSON {json_file}: {e}") from e

    data["_source_file"] = str(json_file)
    return data


def collect_calculate_data(asset_lens_path: str) -> dict[str, Any]:
    """Run `make calculate` via asset-lens and return the report data.

    Uses CalculateReportGenerator from asset_lens if importable,
    otherwise falls back to running `make calculate` as a subprocess.

    Args:
        asset_lens_path: Path to the asset-lens project directory.

    Returns:
        A dictionary with the calculate report data.

    Raises:
        DataCollectorError: If data cannot be collected.
    """
    path = _find_asset_lens_path(asset_lens_path)

    # Try importing from asset_lens directly
    try:
        from asset_lens.data.csv_parser import CSVParser
        from asset_lens.data.models import Portfolio
        from asset_lens.report.calculate_report import CalculateReportGenerator

        from datetime import datetime
        from decimal import Decimal

        products = CSVParser.load_data()
        data_dir = path / "data" / "sample_data"
        try:
            usd_rate, hkd_rate = CSVParser.get_exchange_rates(data_dir)
        except (ValueError, KeyError, TypeError):
            from asset_lens.config import config
            usd_rate = config.default_usd_rate
            hkd_rate = config.default_hkd_rate

        portfolio = Portfolio(
            products=products,
            usd_rate=Decimal(str(usd_rate)),
            hkd_rate=Decimal(str(hkd_rate)),
        )

        reference_date = datetime.now()
        from asset_lens.data.parsers.investment_calculator import InvestmentCalculator
        for product in portfolio.products:
            InvestmentCalculator.calculate_product_returns(product, reference_date)

        generator = CalculateReportGenerator()
        report = generator.generate_calculate_report(portfolio)

        # Convert Decimal values to strings for JSON serialization
        return _serialize_decimals(report)

    except ImportError as e:
        logger.info("Cannot import asset_lens directly (%s), falling back to subprocess", e)

    # Fallback: run as subprocess
    try:
        result = _run_make_command(path, "calculate")
        return {"raw_output": result, "_source": "subprocess"}
    except (subprocess.SubprocessError, FileNotFoundError) as e:
        raise DataCollectorError(f"Failed to run `make calculate`: {e}") from e


def collect_compare_data(asset_lens_path: str, days: int = 7) -> dict[str, Any]:
    """Run compare analysis for trend data.

    Args:
        asset_lens_path: Path to the asset-lens project directory.
        days: Number of days to compare (default 7).

    Returns:
        A dictionary with compare data.

    Raises:
        DataCollectorError: If data cannot be collected.
    """
    path = _find_asset_lens_path(asset_lens_path)

    try:
        result = _run_make_command(path, "compare")
        return {"raw_output": result, "_source": "subprocess", "days": days}
    except (subprocess.SubprocessError, FileNotFoundError) as e:
        logger.warning("Failed to run compare: %s", e)
        return {"raw_output": "", "_source": "unavailable", "days": days, "error": str(e)}


def format_portfolio_context(data: dict[str, Any]) -> str:
    """Format collected data into a structured context string for the agents.

    Args:
        data: The analysis data dictionary from collect_analysis_data().

    Returns:
        A formatted text summary suitable for LLM consumption.
    """
    lines: list[str] = []

    # Critical context for analysts
    lines.append("⚠️ 分析注意事项：")
    lines.append("1. 部分产品为美元/港元计价（标注$或HK$），评估金额时请换算为人民币")
    lines.append("2. 年化收益率不等于实际收益率——投资天数短的产品的实际亏损/收益远小于年化值")
    lines.append(f"3. 当前1年期存款基准利率仅{settings.CN_DEPOSIT_RATE}%，判断低效产品时应以此为准，而非2.0%")
    lines.append("4. 重点关注产品持有期限和实际收益，而非仅看年化数字")
    lines.append("")

    # Portfolio summary
    summary = data.get("portfolio_summary", {})
    if summary:
        lines.append("=== 投资组合概览 ===")
        lines.append(f"总产品数: {summary.get('total_products', 'N/A')}")
        lines.append(f"当前总资产: {summary.get('total_value', 'N/A')}元")
        lines.append(f"总投入资金: {summary.get('total_initial', 'N/A')}元")
        lines.append(f"其中有效投资: {summary.get('valid_initial', 'N/A')}元")
        lines.append(f"未实现收益: {summary.get('total_profit', 'N/A')}元")
        lines.append(f"整体收益率: {summary.get('overall_return_rate', 'N/A')}")
        lines.append(f"有效投资收益率: {summary.get('valid_return_rate', 'N/A')}")
        lines.append(f"正收益产品平均年化: {summary.get('positive_avg_return', 'N/A')}")
        lines.append("")

    # Exchange rates
    rates = data.get("exchange_rates", {})
    usd_rate = float(rates.get('usd_rate', 7.2))
    hkd_rate = float(rates.get('hkd_rate', 0.92))
    if rates:
        lines.append("=== 汇率信息 ===")
        lines.append(f"美元汇率: {usd_rate:.4f} CNY/USD")
        lines.append(f"港元汇率: {hkd_rate:.4f} CNY/HKD")
        lines.append("")

    def _is_foreign(p: dict) -> tuple[str, float]:
        """Detect foreign currency products. Returns (symbol, rate)."""
        name = p.get("name", "")
        ptype = p.get("type", p.get("investment_type", ""))
        if any(kw in name for kw in ["美元", "USD", "QQQ", "Invesco", "富达"]) or "美股" in ptype or "美元" in ptype:
            return ("$", usd_rate)
        if any(kw in name for kw in ["港元", "HKD", "港招"]) or "港元" in ptype:
            return ("HK$", hkd_rate)
        return ("¥", 1.0)

    def _fmt_amount(amt, symbol, rate):
        """Format amount with currency, show CNY equivalent for foreign."""
        if symbol == "¥":
            return f"{symbol}{amt:.2f}"
        cny = float(amt) * rate
        return f"{symbol}{amt:.2f}（≈¥{cny:.2f}）"

    # Top performers
    top = data.get("top_performers", [])
    if top:
        lines.append("=== 收益率排名前10 ===")
        for i, p in enumerate(top, 1):
            name = p.get("name", "未知")
            ret = p.get("return_rate", "N/A")
            amt = p.get("current_amount", 0)
            days = p.get("investment_days", p.get("days", ""))
            sym, rate = _is_foreign(p)
            amt_str = _fmt_amount(float(amt), sym, rate)
            day_str = f", 持有{days}天" if days else ""
            lines.append(f"  {i}. {name}: 年化{ret}, 金额{amt_str}{day_str}")
        lines.append("")

    # Low returns
    low = data.get("low_returns", [])
    if low:
        lines.append("=== 低收益/亏损产品 ===")
        lines.append(f"（注意：年化亏损≠实际亏损；当前存款基准利率为{settings.CN_DEPOSIT_RATE}%，低于此值才需考虑赎回）")
        for p in low[:10]:
            name = p.get("name", "未知")
            ret = p.get("return_rate", p.get("annual_return", "N/A"))
            amt = p.get("current_amount", 0)
            days = p.get("investment_days", p.get("days", ""))
            profit = p.get("profit", p.get("total_profit", ""))
            sym, rate = _is_foreign(p)
            amt_str = _fmt_amount(float(amt), sym, rate)
            day_str = f", 持有{days}天" if days else ""
            profit_str = f", 实际盈亏{profit}元" if profit else ""
            lines.append(f"  - {name}: 年化{ret}{day_str}{profit_str}, 金额{amt_str}")
        lines.append("")

    # Short term observation
    short_term = data.get("short_term_observation", [])
    if short_term:
        lines.append("=== 短期投资观察 ===")
        for p in short_term[:10]:
            name = p.get("name", "未知")
            days = p.get("investment_days", p.get("days", "N/A"))
            ret = p.get("return_rate", p.get("annual_return", "N/A"))
            lines.append(f"  - {name}: 投资{days}天, 收益{ret}")
        lines.append("")

    # Type distribution
    type_dist = data.get("type_distribution", {})
    if type_dist:
        lines.append("=== 投资类型分布 ===")
        for type_name, stats in type_dist.items():
            if isinstance(stats, dict):
                pct = stats.get("percentage", "N/A")
                val = stats.get("total_value", "N/A")
                cnt = stats.get("count", "N/A")
                lines.append(f"  {type_name}: 占比{pct}%, 金额¥{val}, {cnt}个")
            else:
                lines.append(f"  {type_name}: {stats}")
        lines.append("")

    # Risk distribution
    risk_dist = data.get("risk_distribution", {})
    if risk_dist:
        lines.append("=== 风险等级分布 ===")
        for risk_name, stats in risk_dist.items():
            if isinstance(stats, dict):
                pct = stats.get("percentage", "N/A")
                val = stats.get("total_value", "N/A")
                lines.append(f"  {risk_name}: 占比{pct}%, 金额¥{val}")
            else:
                lines.append(f"  {risk_name}: {stats}")
        lines.append("")

    # Risk warnings
    warnings = data.get("risk_warnings", [])
    if warnings:
        lines.append("=== 风险警告 ===")
        for w in warnings:
            msg = w.get("message", str(w))
            lines.append(f"  ⚠️ {msg}")
            products = w.get("products", [])
            for p in products[:5]:
                if isinstance(p, dict):
                    name = p.get("name", "未知")
                    lines.append(f"    - {name}")
        lines.append("")

    # Optimization suggestions
    suggestions = data.get("optimization_suggestions", [])
    if suggestions:
        lines.append("=== 优化建议 ===")
        for i, s in enumerate(suggestions, 1):
            title = s.get("title", str(s))
            lines.append(f"  {i}. {title}")
            details = s.get("details", [])
            for d in details[:5]:
                if d:
                    lines.append(f"     • {d}")
        lines.append("")

    # Investment advice
    advice = data.get("investment_advice", [])
    if advice:
        lines.append("=== 投资建议 ===")
        for a in advice[:10]:
            if isinstance(a, dict):
                lines.append(f"  • {a.get('title', a.get('message', str(a)))}")
            else:
                lines.append(f"  • {a}")
        lines.append("")

    # Comprehensive evaluation
    evaluation = data.get("comprehensive_evaluation", {})
    if evaluation:
        lines.append("=== 综合评价 ===")
        lines.append(f"总当前金额: {evaluation.get('total_current_amount', 'N/A')}元")
        lines.append(f"总投入本金: {evaluation.get('total_investment', 'N/A')}元")
        lines.append(f"已实现收益: {evaluation.get('realized_profit', 'N/A')}元")
        lines.append(f"未实现收益: {evaluation.get('unrealized_profit', 'N/A')}元")
        lines.append(f"整体收益率: {evaluation.get('overall_return_rate', 'N/A')}")
        lines.append(f"加权年化收益率: {evaluation.get('weighted_annual_return', 'N/A')}")
        lines.append(f"时间加权年化收益率: {evaluation.get('time_weighted_return', 'N/A')}")
        eval_text = evaluation.get("evaluation", "")
        if eval_text:
            lines.append(f"评价: {eval_text}")
        lines.append("")

    # Time group analysis
    time_group = data.get("time_group_analysis", {})
    if time_group and time_group.get("groups"):
        lines.append("=== 按投资时间分组 ===")
        for g in time_group["groups"]:
            lines.append(
                f"  {g.get('name', 'N/A')}: {g.get('count', 0)}个, "
                f"金额¥{g.get('total_amount', 'N/A')}, "
                f"收益¥{g.get('total_profit', 'N/A')}, "
                f"平均年化{g.get('avg_return_rate', 'N/A')}"
            )
        lines.append("")

    # Products detail (abbreviated)
    products = data.get("products", [])
    if products:
        lines.append(f"=== 产品详情 (共{len(products)}个) ===")
        for p in products[:30]:
            name = p.get("name", "未知")
            ptype = p.get("investment_type", p.get("type", "未知"))
            annual = p.get("annual_return", p.get("compound_return", "N/A"))
            actual = p.get("return_rate", "N/A")
            amt = p.get("current_amount", "N/A")
            days = p.get("investment_days", "N/A")
            risk = p.get("risk_level", "")
            line = f"  - {name} ({ptype}): 年化{annual}%, 实际{actual}%, 金额¥{amt}, {days}天"
            if risk:
                line += f", 风险:{risk}"
            lines.append(line)
        if len(products) > 30:
            lines.append(f"  ... 还有{len(products) - 30}个产品")
        lines.append("")

    return "\n".join(lines)


def extract_market_snapshot(asset_csv_path: str, weeks: int = 4) -> str:
    """Extract recent market index trends from the asset summary CSV.

    Args:
        asset_csv_path: Path to 资产汇总-表格 1.csv.
        weeks: Number of recent weeks to include.

    Returns:
        Formatted market snapshot string.
    """
    import csv
    from collections import OrderedDict

    indices = OrderedDict([
        ("上证指数", "上证"),
        ("沪深300", "沪深300"),
        ("中证500", "中证500"),
        ("纳指100", "纳指100"),
        ("标普500", "标普500"),
        ("黄金GLD", "黄金GLD"),
        ("美联基利率", "利率"),
        ("恐慌VXX", "恐慌"),
    ])

    try:
        with open(asset_csv_path, encoding="utf-8") as f:
            reader = list(csv.DictReader(f))

        recent = reader[-weeks:] if len(reader) >= weeks else reader

        lines = [
            "=== 近期市场指数趋势 ===（最近4周周度数据）",
            "",
        ]

        for csv_key, label in indices.items():
            values = []
            for row in recent:
                date = row.get("日期", "")
                val = row.get(csv_key, "").rstrip("%")
                if val and val != "0":
                    values.append((date, val))

            if len(values) < 2:
                continue

            first_val = float(values[0][1])
            last_val = float(values[-1][1])
            change = last_val - first_val
            pct = (change / first_val) * 100 if first_val != 0 else 0
            trend = "↑" if change > 0 else "↓" if change < 0 else "→"

            lines.append(
                f"  {label}: {values[0][1]} → {values[-1][1]} "
                f"({trend}{abs(pct):.1f}%, {len(values)}周)"
            )

        lines.append("")
        lines.append("⚠️ 请结合以上指数趋势判断下周市场方向，给出前瞻性分析")
        lines.append("")
        lines.append("=== 国内利率环境 ===")
        lines.append(f"  当前中国1年期存款基准利率: {settings.CN_DEPOSIT_RATE}%")
        lines.append(f"  当前1年期LPR（贷款市场报价利率）: {settings.CN_LPR_RATE}%")
        lines.append(f"  当前10年期国债收益率: {settings.CN_BOND_YIELD}%")
        lines.append("  美联储联邦基金利率: 见上方趋势数据")
        depo = settings.CN_DEPOSIT_RATE
        if depo < 2.0:
            lines.append("  ⚠️ 国内低利率环境下，债券/理财产品收益持续承压，红利/高股息策略相对吸引力上升")
        return "\n".join(lines)

    except Exception as e:
        logger.warning("Failed to read market data: %s", e)
        return ""


def extract_recent_transactions(csv_path: str, days: int = 60) -> list[dict[str, Any]]:
    """Extract recent buy/sell transactions from the 投资产品 CSV.

    Args:
        csv_path: Path to 投资产品-表格 1.csv.
        days: Look-back window in days (default 60).

    Returns:
        List of recent transaction dicts with name, date, action, amount.
    """
    from datetime import datetime, timedelta

    cutoff = datetime.now() - timedelta(days=days)
    recent: list[dict[str, Any]] = []

    try:
        import csv
        with open(csv_path, encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                name = row.get("名称", "").strip()
                tx_field = row.get("交易记录", "").strip()
                if not tx_field:
                    continue

                # Parse: "2025/09/15:buy:20000; 2025/12/30:buy:10000; 2026/05/26:buy:10000"
                for entry in tx_field.split(";"):
                    entry = entry.strip()
                    if not entry:
                        continue
                    parts = entry.split(":")
                    if len(parts) < 3:
                        continue
                    date_str, action, amount_str = parts[0], parts[1], parts[2]
                    try:
                        tx_date = datetime.strptime(date_str, "%Y/%m/%d")
                    except ValueError:
                        continue
                    if tx_date >= cutoff:
                        recent.append({
                            "product": name,
                            "date": date_str,
                            "action": "买入" if action.strip() == "buy" else "卖出",
                            "amount": float(amount_str),
                        })
    except Exception as e:
        logger.warning("Failed to read transaction CSV: %s", e)
        return []

    # Sort by date descending, most recent first
    recent.sort(key=lambda x: x["date"], reverse=True)
    return recent


def format_transaction_context(transactions: list[dict[str, Any]]) -> str:
    """Format recent transactions into a readable context string."""
    if not transactions:
        return ""

    # Show top 25 most recent, summarize the rest
    display = transactions[:25]

    lines = [
        "=== 近期交易记录（最近60天） ===",
        "以下产品在最近两个月内有买入/卖出操作，分析时请考虑交易时点和频率：",
        "",
    ]
    for tx in display:
        lines.append(f"  {tx['date']}: {tx['action']}「{tx['product']}」{tx['amount']:.0f}元")

    if len(transactions) > 25:
        lines.append(f"  ... 还有{len(transactions) - 25}笔交易")

    # Summarize patterns
    buys = sum(1 for t in transactions if t["action"] == "买入")
    sells = sum(1 for t in transactions if t["action"] == "卖出")
    buy_amt = sum(t["amount"] for t in transactions if t["action"] == "买入")
    sell_amt = sum(t["amount"] for t in transactions if t["action"] == "卖出")

    lines.append("")
    lines.append(f"  总结：共{buys}笔买入(¥{buy_amt:.0f})，{sells}笔卖出(¥{sell_amt:.0f})，净{'流入' if buy_amt > sell_amt else '流出'}¥{abs(buy_amt - sell_amt):.0f}")
    lines.append("")
    return "\n".join(lines)


def _run_make_command(project_path: Path, target: str) -> str:
    """Run a make command in the asset-lens project directory.

    Args:
        project_path: Path to the asset-lens project.
        target: Make target to run (e.g., 'calculate', 'analyze').

    Returns:
        The stdout output of the command.

    Raises:
        subprocess.SubprocessError: If the command fails.
    """
    result = subprocess.run(
        ["make", target],
        cwd=str(project_path),
        capture_output=True,
        text=True,
        timeout=300,
    )
    if result.returncode != 0:
        raise subprocess.SubprocessError(
            f"`make {target}` failed with exit code {result.returncode}: {result.stderr}"
        )
    return result.stdout


def _serialize_decimals(obj: Any) -> Any:
    """Recursively convert Decimal values to strings for JSON serialization."""
    from decimal import Decimal

    if isinstance(obj, Decimal):
        return str(obj)
    if isinstance(obj, dict):
        return {k: _serialize_decimals(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_serialize_decimals(item) for item in obj]
    return obj
