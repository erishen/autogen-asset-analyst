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
    if rates:
        lines.append("=== 汇率信息 ===")
        lines.append(f"美元汇率: {rates.get('usd_rate', 'N/A')} CNY/USD")
        lines.append(f"港元汇率: {rates.get('hkd_rate', 'N/A')} CNY/HKD")
        lines.append("")

    # Top performers
    top = data.get("top_performers", [])
    if top:
        lines.append("=== 收益率排名前10 ===")
        for i, p in enumerate(top, 1):
            name = p.get("name", "未知")
            ret = p.get("return_rate", "N/A")
            amt = p.get("current_amount", "N/A")
            lines.append(f"  {i}. {name}: 年化{ret}, 金额¥{amt}")
        lines.append("")

    # Low returns
    low = data.get("low_returns", [])
    if low:
        lines.append("=== 低收益产品 ===")
        for p in low[:10]:
            name = p.get("name", "未知")
            ret = p.get("return_rate", p.get("annual_return", "N/A"))
            amt = p.get("current_amount", "N/A")
            lines.append(f"  - {name}: 年化{ret}, 金额¥{amt}")
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
