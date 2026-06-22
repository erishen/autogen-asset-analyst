"""Investment Research Roundtable orchestration using AutoGen multi-agent conversation.

Unlike a deterministic pipeline, this module leverages AutoGen's conversational
multi-agent strength. Four agents with different investment perspectives debate
and reach consensus on portfolio decisions.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path
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
    extract_market_snapshot,
    extract_recent_transactions,
    format_portfolio_context,
    format_transaction_context,
)
from autogen_asset_analyst.knowledge_retriever import (
    format_knowledge_context,
    retrieve_personal_knowledge,
)
from autogen_asset_analyst.config import settings

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


def _build_initial_message(portfolio_context: str, knowledge_context: str = "", tx_context: str = "", market_context: str = "") -> str:
    """Build the initial message for the roundtable discussion.

    Args:
        portfolio_context: Formatted portfolio data from DataCollector.
        knowledge_context: Optional personal investment knowledge from RAG.
        tx_context: Optional recent transaction records.
        market_context: Optional market index trends.

    Returns:
        The initial message to start the roundtable.
    """
    msg = (
        "各位分析师，欢迎参加今天的投资研究圆桌会议。\n\n"
        "以下是当前投资组合的详细数据：\n\n"
        f"{portfolio_context}\n\n"
    )

    if market_context:
        msg += f"{market_context}\n\n"

    if tx_context:
        msg += (
            f"{tx_context}\n\n"
        )

    if knowledge_context:
        msg += (
            f"{knowledge_context}\n\n"
            "⚠️ 重要：以上是投资人的个人知识库，反映了其投资偏好、经验风格和长期目标。"
            "所有分析建议必须基于投资人的实际偏好，不能仅凭短期数据做决策。"
            "如果投资人有长期持有的偏好，短期亏损不应成为清仓理由。\n\n"
        )

    msg += (
        "请各位从自己的专业角度进行分析和讨论。讨论目标：\n\n"
        "**必须产出以下内容：**\n"
        "1. 列出当前组合 Top 5 值得继续持有/加仓的产品，说明理由和预期收益\n"
        "2. 列出需要减仓或赎回的 Top 5 产品，说明止损原因\n"
        "3. 给出下周具体的调仓建议（产品名称 + 操作 + 金额区间）\n"
        "4. 优先级排序：哪些操作应该立即执行，哪些可以观察\n\n"
        "请各位畅所欲言，充分讨论。投资总监将在讨论充分后总结共识。"
    )
    return msg


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

    # Step 2: Extract market snapshot for forward-looking analysis
    market_context = ""
    try:
        csv_path = Path(asset_lens_path).parent / "ts-demo" / "data" / f"money_csv_{date}" / "资产汇总-表格 1.csv"
        if not csv_path.exists():
            import glob
            candidates = sorted(glob.glob(str(Path(asset_lens_path).parent / "ts-demo" / "data" / "money_csv_*")))
            if candidates:
                csv_path = Path(candidates[-1]) / "资产汇总-表格 1.csv"
        if csv_path.exists():
            market_context = extract_market_snapshot(str(csv_path))
            if market_context:
                logger.info("Market snapshot extracted")
    except Exception as e:
        logger.warning("Failed to extract market snapshot: %s", e)

    # Step 3: Extract recent transaction records
    tx_context = ""
    try:
        csv_path = Path(asset_lens_path).parent / "ts-demo" / "data" / f"money_csv_{date}" / "投资产品-表格 1.csv"
        if not csv_path.exists():
            # Try latest data directory
            import glob
            candidates = sorted(glob.glob(str(Path(asset_lens_path).parent / "ts-demo" / "data" / "money_csv_*")))
            if candidates:
                csv_path = Path(candidates[-1]) / "投资产品-表格 1.csv"
        if csv_path.exists():
            transactions = extract_recent_transactions(str(csv_path))
            tx_context = format_transaction_context(transactions)
            if tx_context:
                logger.info("Recent transactions extracted: %d records", len(transactions))
        else:
            logger.debug("Transaction CSV not found at %s", csv_path)
    except Exception as e:
        logger.warning("Failed to extract transactions: %s", e)

    # Step 3: Retrieve personal investment knowledge from RAG
    knowledge_context = ""
    kb_path = settings.KNOWLEDGE_BASE_PATH
    if kb_path:
        try:
            knowledge = retrieve_personal_knowledge(kb_path)
            knowledge_context = format_knowledge_context(knowledge)
            if knowledge_context:
                logger.info("Personal knowledge retrieved and formatted")
        except Exception as e:
            logger.warning("Failed to retrieve personal knowledge: %s", e)

    # Step 3: Format context for agents
    portfolio_context = format_portfolio_context(portfolio_data)

    # Step 4: Create model client and agents
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

    # Step 5: Build initial message (with personal knowledge) and run conversation
    initial_message = _build_initial_message(portfolio_context, knowledge_context, tx_context, market_context)

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
