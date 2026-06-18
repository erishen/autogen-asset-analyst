"""Visualization module for the Investment Research Roundtable HTML report.

Generates a self-contained HTML report that clearly shows the DEBATE nature
of the roundtable, with different colored sections for each agent.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

import markdown as md_lib

from autogen_asset_analyst.analyzer import RoundtableResult

# Agent visual configuration
AGENT_CONFIG = {
    "ValueInvestorAgent": {
        "name": "价值投资分析师",
        "avatar": "🏦",
        "color": "#2563eb",
        "bg_color": "#eff6ff",
        "border_color": "#93c5fd",
    },
    "TechnicalAnalystAgent": {
        "name": "技术分析师",
        "avatar": "📈",
        "color": "#059669",
        "bg_color": "#ecfdf5",
        "border_color": "#6ee7b7",
    },
    "RiskControllerAgent": {
        "name": "风险控制官",
        "avatar": "🛡️",
        "color": "#dc2626",
        "bg_color": "#fef2f2",
        "border_color": "#fca5a5",
    },
    "InvestmentDirectorAgent": {
        "name": "投资总监",
        "avatar": "👔",
        "color": "#7c3aed",
        "bg_color": "#f5f3ff",
        "border_color": "#c4b5fd",
    },
}


def _format_markdown_text(text: str) -> str:
    """Convert Markdown text to HTML."""
    if not text:
        return ""
    return md_lib.markdown(text, extensions=["extra", "nl2br"])


def _build_summary_cards(portfolio_data: dict[str, Any]) -> str:
    """Build portfolio summary cards HTML.

    Args:
        portfolio_data: The analysis data from DataCollector.

    Returns:
        HTML string for the summary cards section.
    """
    summary = portfolio_data.get("portfolio_summary", {})
    if not summary:
        return ""

    cards_html = f"""
    <div class="stats-grid">
        <div class="stat-card" style="border-left-color: #2563eb;">
            <div class="stat-value">{summary.get('total_value', 'N/A')}</div>
            <div class="stat-label">当前总资产(元)</div>
        </div>
        <div class="stat-card" style="border-left-color: #059669;">
            <div class="stat-value">{summary.get('total_profit', 'N/A')}</div>
            <div class="stat-label">未实现收益(元)</div>
        </div>
        <div class="stat-card" style="border-left-color: #7c3aed;">
            <div class="stat-value">{summary.get('overall_return_rate', 'N/A')}</div>
            <div class="stat-label">整体收益率</div>
        </div>
        <div class="stat-card" style="border-left-color: #f59e0b;">
            <div class="stat-value">{summary.get('positive_avg_return', 'N/A')}</div>
            <div class="stat-label">正收益平均年化</div>
        </div>
    </div>"""

    # Type distribution
    type_dist = portfolio_data.get("type_distribution", {})
    if type_dist:
        type_items = []
        for type_name, stats in type_dist.items():
            if isinstance(stats, dict):
                pct = stats.get("percentage", "N/A")
                type_items.append(
                    f'<span class="type-badge" style="background: #f1f5f9; color: #475569;">'
                    f"{type_name} {pct}%</span>"
                )
        if type_items:
            cards_html += f"""
            <div class="type-distribution">
                <div class="section-label">投资类型分布</div>
                <div class="type-badges">{''.join(type_items)}</div>
            </div>"""

    # Risk distribution
    risk_dist = portfolio_data.get("risk_distribution", {})
    if risk_dist:
        risk_items = []
        for risk_name, stats in risk_dist.items():
            if isinstance(stats, dict):
                pct = stats.get("percentage", "N/A")
                risk_items.append(
                    f'<span class="type-badge" style="background: #fef2f2; color: #991b1b;">'
                    f"{risk_name} {pct}%</span>"
                )
        if risk_items:
            cards_html += f"""
            <div class="type-distribution">
                <div class="section-label">风险等级分布</div>
                <div class="type-badges">{''.join(risk_items)}</div>
            </div>"""

    return cards_html


def _build_discussion_transcript(messages: list[dict[str, str]]) -> str:
    """Build the discussion transcript HTML with agent-colored sections.

    Args:
        messages: List of agent messages with source and content.

    Returns:
        HTML string for the discussion transcript.
    """
    if not messages:
        return '<div class="empty-state">暂无讨论记录</div>'

    transcript_parts = []
    for i, msg in enumerate(messages, 1):
        source = msg.get("source", "Unknown")
        content = msg.get("content", "")
        config = AGENT_CONFIG.get(source, {
            "name": source,
            "avatar": "💬",
            "color": "#64748b",
            "bg_color": "#f8fafc",
            "border_color": "#cbd5e1",
        })

        # Check for veto
        is_veto = source == "RiskControllerAgent" and "【否决】" in content
        veto_badge = '<span class="veto-badge">否决</span>' if is_veto else ""

        # Truncate very long messages for display
        display_content = content
        if len(content) > 3000:
            display_content = content[:3000] + "\n\n...(内容过长已截断)"

        content_html = _format_markdown_text(display_content)

        transcript_parts.append(f"""
        <div class="message-card" style="border-left: 4px solid {config['border_color']}; background: {config['bg_color']};">
            <div class="message-header">
                <span class="agent-avatar">{config['avatar']}</span>
                <span class="agent-name" style="color: {config['color']};">{config['name']}</span>
                <span class="message-index">#{i}</span>
                {veto_badge}
            </div>
            <div class="message-content">{content_html}</div>
        </div>""")

    return "\n".join(transcript_parts)


def _build_consensus_section(result: RoundtableResult) -> str:
    """Build the consensus decisions section HTML.

    Args:
        result: The roundtable result.

    Returns:
        HTML string for the consensus section.
    """
    if not result.consensus:
        return ""

    consensus_html = _format_markdown_text(result.consensus)

    vetoes_html = ""
    if result.vetoes:
        veto_items = []
        for v in result.vetoes:
            veto_items.append(
                f'<div class="veto-item">{_format_markdown_text(v["content"])}</div>'
            )
        vetoes_html = f"""
        <div class="vetoes-section">
            <h3>🛡️ 风险否决记录</h3>
            {''.join(veto_items)}
        </div>"""

    return f"""
    <div class="consensus-section">
        <h2>📋 共识决策</h2>
        <div class="consensus-content">{consensus_html}</div>
        {vetoes_html}
    </div>"""


def _build_risk_warnings_section(portfolio_data: dict[str, Any]) -> str:
    """Build the risk warnings section HTML.

    Args:
        portfolio_data: The analysis data from DataCollector.

    Returns:
        HTML string for the risk warnings section.
    """
    warnings = portfolio_data.get("risk_warnings", [])
    if not warnings:
        return ""

    warning_items = []
    for w in warnings:
        msg = w.get("message", str(w))
        products = w.get("products", [])
        product_list = ""
        if products:
            product_names = []
            for p in products[:5]:
                if isinstance(p, dict):
                    product_names.append(p.get("name", "未知"))
            if product_names:
                product_list = f'<div class="warning-products">涉及: {", ".join(product_names)}</div>'

        warning_items.append(f"""
        <div class="warning-item">
            <div class="warning-message">⚠️ {msg}</div>
            {product_list}
        </div>""")

    return f"""
    <div class="risk-warnings-section">
        <h2>⚠️ 风险警告</h2>
        {''.join(warning_items)}
    </div>"""


def generate_html_report(
    result: RoundtableResult,
    asset_lens_path: str = "",
) -> str:
    """Generate a self-contained HTML report for the roundtable discussion.

    The report clearly shows the DEBATE nature with different colored
    sections for each agent, plus consensus decisions and risk warnings.

    Args:
        result: The RoundtableResult from the discussion.
        asset_lens_path: Path to the asset-lens data source.

    Returns:
        A complete HTML string.
    """
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    portfolio_data = result.portfolio_data

    summary_cards = _build_summary_cards(portfolio_data)
    transcript = _build_discussion_transcript(result.messages)
    consensus = _build_consensus_section(result)
    risk_warnings = _build_risk_warnings_section(portfolio_data)

    # Agent legend
    legend_items = []
    for agent_key, config in AGENT_CONFIG.items():
        legend_items.append(
            f'<span class="legend-item" style="color: {config["color"]};">'
            f'{config["avatar"]} {config["name"]}</span>'
        )
    legend_html = " | ".join(legend_items)

    html = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>投资研究圆桌会议报告</title>
    <style>
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Noto Sans SC', sans-serif;
            background-color: #f8fafc;
            color: #1e293b;
            line-height: 1.6;
        }}
        .header {{
            background: linear-gradient(135deg, #1e3a5f, #2563eb, #7c3aed);
            color: white;
            padding: 2.5rem 2rem;
            text-align: center;
        }}
        .header h1 {{ font-size: 1.8rem; margin-bottom: 0.5rem; letter-spacing: 0.05em; }}
        .header .subtitle {{ opacity: 0.9; font-size: 0.95rem; }}
        .header .meta {{
            margin-top: 1rem;
            font-size: 0.85rem;
            opacity: 0.8;
        }}
        .container {{
            max-width: 1100px;
            margin: 0 auto;
            padding: 2rem;
        }}
        .section {{
            background: white;
            border-radius: 12px;
            padding: 1.5rem;
            margin-bottom: 1.5rem;
            box-shadow: 0 1px 3px rgba(0,0,0,0.08);
        }}
        .section h2 {{
            font-size: 1.2rem;
            margin-bottom: 1rem;
            padding-bottom: 0.5rem;
            border-bottom: 2px solid #e2e8f0;
            color: #1e293b;
        }}
        .section-label {{
            font-size: 0.85rem;
            color: #64748b;
            margin-bottom: 0.5rem;
            font-weight: 600;
        }}
        .stats-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 1rem;
            margin-bottom: 1.5rem;
        }}
        .stat-card {{
            background: #f8fafc;
            border-radius: 8px;
            padding: 1rem;
            text-align: center;
            border-left: 4px solid #e2e8f0;
        }}
        .stat-value {{
            font-size: 1.3rem;
            font-weight: 700;
            color: #1e293b;
        }}
        .stat-label {{
            font-size: 0.8rem;
            color: #64748b;
            margin-top: 0.25rem;
        }}
        .type-distribution {{
            margin-top: 1rem;
        }}
        .type-badges {{
            display: flex;
            flex-wrap: wrap;
            gap: 0.5rem;
        }}
        .type-badge {{
            padding: 0.25rem 0.75rem;
            border-radius: 9999px;
            font-size: 0.8rem;
            font-weight: 500;
        }}
        .legend {{
            display: flex;
            flex-wrap: wrap;
            gap: 1rem;
            justify-content: center;
            padding: 1rem;
            background: white;
            border-radius: 12px;
            margin-bottom: 1.5rem;
            box-shadow: 0 1px 3px rgba(0,0,0,0.08);
        }}
        .legend-item {{
            font-weight: 600;
            font-size: 0.9rem;
        }}
        .message-card {{
            border-radius: 8px;
            padding: 1rem 1.25rem;
            margin-bottom: 1rem;
        }}
        .message-header {{
            display: flex;
            align-items: center;
            gap: 0.5rem;
            margin-bottom: 0.75rem;
        }}
        .agent-avatar {{
            font-size: 1.2rem;
        }}
        .agent-name {{
            font-weight: 700;
            font-size: 0.95rem;
        }}
        .message-index {{
            font-size: 0.75rem;
            color: #94a3b8;
            margin-left: auto;
        }}
        .veto-badge {{
            background: #dc2626;
            color: white;
            font-size: 0.7rem;
            padding: 0.15rem 0.5rem;
            border-radius: 9999px;
            font-weight: 700;
            animation: pulse 2s infinite;
        }}
        @keyframes pulse {{
            0%, 100% {{ opacity: 1; }}
            50% {{ opacity: 0.7; }}
        }}
        .message-content {{
            color: #334155;
            line-height: 1.8;
            font-size: 0.9rem;
        }}
        .message-content h1 {{ font-size: 1.1rem; margin: 0.8rem 0 0.4rem; color: #1e293b; }}
        .message-content h2 {{ font-size: 1.05rem; margin: 0.8rem 0 0.4rem; color: #1e293b; }}
        .message-content h3 {{ font-size: 1rem; margin: 0.6rem 0 0.3rem; color: #334155; }}
        .message-content p {{ margin: 0.4rem 0; }}
        .message-content ul, .message-content ol {{ margin: 0.4rem 0; padding-left: 1.5rem; }}
        .message-content li {{ margin: 0.2rem 0; }}
        .message-content strong {{ color: #1e293b; }}
        .message-content em {{ color: #64748b; }}
        .consensus-section {{
            background: white;
            border-radius: 12px;
            padding: 1.5rem;
            margin-bottom: 1.5rem;
            box-shadow: 0 1px 3px rgba(0,0,0,0.08);
            border: 2px solid #7c3aed;
        }}
        .consensus-section h2 {{
            color: #7c3aed;
            border-bottom-color: #c4b5fd;
        }}
        .consensus-content {{
            color: #334155;
            line-height: 1.8;
        }}
        .consensus-content h1 {{ font-size: 1.1rem; margin: 0.8rem 0 0.4rem; color: #1e293b; }}
        .consensus-content h2 {{ font-size: 1.05rem; margin: 0.8rem 0 0.4rem; color: #1e293b; }}
        .consensus-content h3 {{ font-size: 1rem; margin: 0.6rem 0 0.3rem; color: #334155; }}
        .consensus-content p {{ margin: 0.4rem 0; }}
        .consensus-content ul, .consensus-content ol {{ margin: 0.4rem 0; padding-left: 1.5rem; }}
        .consensus-content li {{ margin: 0.2rem 0; }}
        .vetoes-section {{
            margin-top: 1.5rem;
            padding: 1rem;
            background: #fef2f2;
            border-radius: 8px;
            border: 1px solid #fca5a5;
        }}
        .vetoes-section h3 {{
            color: #dc2626;
            margin-bottom: 0.75rem;
        }}
        .veto-item {{
            padding: 0.75rem;
            margin-bottom: 0.5rem;
            background: white;
            border-radius: 6px;
            border-left: 3px solid #dc2626;
        }}
        .risk-warnings-section {{
            background: white;
            border-radius: 12px;
            padding: 1.5rem;
            margin-bottom: 1.5rem;
            box-shadow: 0 1px 3px rgba(0,0,0,0.08);
            border: 2px solid #f59e0b;
        }}
        .risk-warnings-section h2 {{
            color: #92400e;
            border-bottom-color: #fde68a;
        }}
        .warning-item {{
            padding: 0.75rem;
            margin-bottom: 0.5rem;
            background: #fffbeb;
            border-radius: 6px;
            border-left: 3px solid #f59e0b;
        }}
        .warning-message {{
            font-weight: 500;
            color: #92400e;
        }}
        .warning-products {{
            font-size: 0.85rem;
            color: #78350f;
            margin-top: 0.25rem;
        }}
        .empty-state {{
            text-align: center;
            padding: 2rem;
            color: #94a3b8;
        }}
        .footer {{
            text-align: center;
            padding: 2rem;
            color: #94a3b8;
            font-size: 0.85rem;
        }}
    </style>
</head>
<body>
    <div class="header">
        <h1>🏛️ 投资研究圆桌会议</h1>
        <div class="subtitle">Investment Research Roundtable</div>
        <div class="meta">
            生成时间: {now} | 数据源: {asset_lens_path or 'asset-lens'}
        </div>
    </div>

    <div class="container">
        <!-- Agent Legend -->
        <div class="legend">
            {legend_html}
        </div>

        <!-- Portfolio Summary -->
        <div class="section">
            <h2>📊 投资组合概览</h2>
            {summary_cards}
        </div>

        <!-- Discussion Transcript -->
        <div class="section">
            <h2>🗣️ 圆桌讨论记录</h2>
            {transcript}
        </div>

        <!-- Consensus Decisions -->
        {consensus}

        <!-- Risk Warnings -->
        {risk_warnings}
    </div>

    <div class="footer">
        Generated by AutoGen Asset Analyst - Investment Research Roundtable
    </div>
</body>
</html>"""

    return html
