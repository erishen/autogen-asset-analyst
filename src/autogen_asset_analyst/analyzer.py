"""Investment Research Roundtable orchestration using AutoGen multi-agent conversation.

Unlike a deterministic pipeline, this module leverages AutoGen's conversational
multi-agent strength. Four agents with different investment perspectives debate
and reach consensus on portfolio decisions.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

from autogen_agentchat.conditions import MaxMessageTermination, TextMentionTermination
from autogen_agentchat.teams import SelectorGroupChat

from autogen_asset_analyst.agents import (
    create_investment_director_agent,
    create_risk_controller_agent,
    create_technical_analyst_agent,
    create_value_investor_agent,
    get_model_client,
)
from autogen_asset_analyst.data_collector import (
    DataCollectorError,
    collect_analysis_data,
    format_portfolio_context,
)

logger = logging.getLogger(__name__)


@dataclass
class RoundtableResult:
    """Result of a roundtable discussion."""

    portfolio_data: dict[str, Any]
    messages: list[dict[str, str]] = field(default_factory=list)
    consensus: str = ""
    risk_warnings: list[str] = field(default_factory=list)
    action_items: list[str] = field(default_factory=list)
    vetoes: list[dict[str, str]] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    token_usage: dict[str, int] = field(default_factory=dict)


def _build_initial_message(portfolio_context: str) -> str:
    """Build the initial message for the roundtable discussion.

    Args:
        portfolio_context: Formatted portfolio data from DataCollector.

    Returns:
        The initial message to start the roundtable.
    """
    return (
        "各位分析师，欢迎参加今天的投资研究圆桌会议。\n\n"
        "以下是当前投资组合的详细数据：\n\n"
        f"{portfolio_context}\n\n"
        "请各位从自己的专业角度进行分析和讨论：\n"
        "1. 价值投资分析师：请从基本面和长期价值角度评估\n"
        "2. 技术分析师：请从趋势和动量角度分析\n"
        "3. 风险控制官：请评估风险敞口和集中度\n"
        "4. 投资总监：请综合各方意见，形成共识决策\n\n"
        "请各位畅所欲言，充分讨论。投资总监将在讨论充分后总结共识。"
    )


def _extract_vetoes(messages: list[dict[str, str]]) -> list[dict[str, str]]:
    """Extract veto decisions from RiskControllerAgent messages.

    Args:
        messages: List of agent messages.

    Returns:
        List of veto records with source and content.
    """
    vetoes = []
    for msg in messages:
        if msg["source"] == "RiskControllerAgent" and "【否决】" in msg["content"]:
            vetoes.append({"source": msg["source"], "content": msg["content"]})
    return vetoes


def _extract_consensus(messages: list[dict[str, str]]) -> str:
    """Extract the final consensus from InvestmentDirectorAgent.

    Args:
        messages: List of agent messages.

    Returns:
        The consensus content, or the last InvestmentDirectorAgent message.
    """
    for msg in reversed(messages):
        if msg["source"] == "InvestmentDirectorAgent":
            return msg["content"]
    return ""


async def run_roundtable_async(
    asset_lens_path: str,
    max_rounds: int = 6,
    date: str | None = None,
) -> RoundtableResult:
    """Run the Investment Research Roundtable discussion asynchronously.

    Args:
        asset_lens_path: Path to the asset-lens project directory.
        max_rounds: Maximum number of discussion rounds (default 6).
        date: Optional date string (YYYYMMDD) to load a specific analysis file.

    Returns:
        A RoundtableResult with the discussion transcript and consensus.
    """
    result = RoundtableResult(portfolio_data={})

    # Step 1: Collect data
    try:
        portfolio_data = collect_analysis_data(asset_lens_path, date=date)
        result.portfolio_data = portfolio_data
    except DataCollectorError as e:
        result.errors.append(f"数据收集失败: {e}")
        logger.error("Data collection failed: %s", e)
        return result

    # Step 2: Format context for agents
    portfolio_context = format_portfolio_context(portfolio_data)

    # Step 3: Create model client and agents
    model_client = get_model_client()

    value_investor = create_value_investor_agent(model_client)
    technical_analyst = create_technical_analyst_agent(model_client)
    risk_controller = create_risk_controller_agent(model_client)
    investment_director = create_investment_director_agent(model_client)

    # Step 4: Build team with SelectorGroupChat
    # SelectorGroupChat uses an LLM to dynamically choose which agent speaks next,
    # enabling natural debate flow (e.g. Risk Controller can interject to veto)
    max_messages = 4 * max_rounds + 4
    termination = TextMentionTermination("ROUNDTABLE_COMPLETE") | MaxMessageTermination(max_messages=max_messages)

    team = SelectorGroupChat(
        participants=[value_investor, technical_analyst, risk_controller, investment_director],
        model_client=model_client,
        termination_condition=termination,
        allow_repeated_speaker=True,
    )

    # Step 5: Build initial message and run conversation
    initial_message = _build_initial_message(portfolio_context)

    logger.info("Starting roundtable discussion with %d rounds max", max_rounds)
    conversation_result = await team.run(task=initial_message)

    # Step 6: Extract messages and token usage
    messages = []
    total_prompt_tokens = 0
    total_completion_tokens = 0
    for msg in conversation_result.messages:
        messages.append({
            "source": msg.source,
            "content": msg.content if isinstance(msg.content, str) else str(msg.content),
        })
        # Extract token usage from message metadata
        if hasattr(msg, "models_usage") and msg.models_usage:
            total_prompt_tokens += msg.models_usage.prompt_tokens
            total_completion_tokens += msg.models_usage.completion_tokens

    result.messages = messages
    token_usage = {
        "prompt_tokens": total_prompt_tokens,
        "completion_tokens": total_completion_tokens,
        "total_tokens": total_prompt_tokens + total_completion_tokens,
    }
    result.token_usage = token_usage

    # Step 7: Extract consensus, vetoes, and other structured data
    result.consensus = _extract_consensus(messages)
    result.vetoes = _extract_vetoes(messages)

    logger.info(
        "Roundtable completed with %d messages, %d vetoes, tokens: %d (prompt=%d, completion=%d)",
        len(messages),
        len(result.vetoes),
        token_usage["total_tokens"],
        total_prompt_tokens,
        total_completion_tokens,
    )

    return result


def run_roundtable(
    asset_lens_path: str,
    max_rounds: int = 6,
    date: str | None = None,
) -> RoundtableResult:
    """Run the Investment Research Roundtable discussion synchronously.

    Args:
        asset_lens_path: Path to the asset-lens project directory.
        max_rounds: Maximum number of discussion rounds (default 6).
        date: Optional date string (YYYYMMDD) to load a specific analysis file.

    Returns:
        A RoundtableResult with the discussion transcript and consensus.
    """
    import asyncio

    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = None

    if loop and loop.is_running():
        import concurrent.futures

        with concurrent.futures.ThreadPoolExecutor() as pool:
            future = pool.submit(asyncio.run, run_roundtable_async(asset_lens_path, max_rounds, date))
            return future.result()
    else:
        return asyncio.run(run_roundtable_async(asset_lens_path, max_rounds, date))
