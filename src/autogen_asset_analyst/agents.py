"""AutoGen agent definitions for the Investment Research Roundtable.

Four agents with distinct investment perspectives debate and reach consensus:
1. ValueInvestorAgent - Long-term fundamentals perspective
2. TechnicalAnalystAgent - Trend/momentum perspective
3. RiskControllerAgent - Risk control with veto power
4. InvestmentDirectorAgent - Moderates and synthesizes consensus
"""

from __future__ import annotations

from autogen_agentchat.agents import AssistantAgent
from autogen_ext.models.openai import OpenAIChatCompletionClient

from autogen_asset_analyst.config import settings


def get_model_client() -> OpenAIChatCompletionClient:
    """Create an OpenAI-compatible model client from settings.

    For non-OpenAI models (e.g. DeepSeek), model_info must be provided
    since AutoGen doesn't recognize them.

    Returns:
        An OpenAIChatCompletionClient instance.
    """
    kwargs: dict = {
        "model": settings.DEFAULT_MODEL,
    }
    if settings.OPENAI_API_KEY:
        kwargs["api_key"] = settings.OPENAI_API_KEY
    if settings.OPENAI_BASE_URL:
        kwargs["base_url"] = settings.OPENAI_BASE_URL

    # For non-OpenAI models like deepseek-chat, provide model_info
    if settings.DEFAULT_MODEL.startswith("deepseek"):
        kwargs["model_info"] = {
            "vision": False,
            "function_calling": True,
            "json_output": True,
            "family": "unknown",
            "structured_output": True,
        }

    return OpenAIChatCompletionClient(**kwargs)


def create_value_investor_agent(model_client: OpenAIChatCompletionClient) -> AssistantAgent:
    """Create the ValueInvestorAgent (价值投资分析师).

    Evaluates from fundamentals perspective. Focuses on long-term value,
    consistent returns, and low-risk products. Argues for holding quality
    products and patience with short-term dips.

    Args:
        model_client: The model client to use.

    Returns:
        An AssistantAgent configured for value investing analysis.
    """
    return AssistantAgent(
        name="ValueInvestorAgent",
        model_client=model_client,
        description="价值投资分析师，从基本面和长期价值角度评估投资组合，主张持有优质产品、耐心对待短期波动。",
        system_message=(
            "你是一位资深的价值投资分析师，你的投资理念深受巴菲特和格雷厄姆的影响。\n\n"
            "你的核心观点：\n"
            "1. 投资的关键是寻找内在价值被低估的优质资产\n"
            "2. 长期持有优质产品，忽略短期市场噪音\n"
            "3. 稳定的年化收益率比短期暴利更重要\n"
            "4. 低风险产品（债券、货币基金、定期存款）是组合的压舱石\n"
            "5. 对于短期波动导致收益下降的产品，应保持耐心\n\n"
            "你在讨论中的立场：\n"
            "- 支持：持有高质量产品、增加低风险配置、长期定投策略\n"
            "- 反对：追逐高收益、过度集中投资、频繁调仓\n\n"
            "⚠️ 你的发言务必简洁：用3-5句话说明核心判断，列出持有/加仓/减仓的具体产品。不要长篇大论。\n\n"
            "请用中文回答，观点鲜明，有理有据。"
        ),
    )


def create_technical_analyst_agent(model_client: OpenAIChatCompletionClient) -> AssistantAgent:
    """Create the TechnicalAnalystAgent (技术分析师).

    Evaluates from trend/momentum perspective. Focuses on return trends,
    momentum signals, and timing. Argues for riding winners and cutting losers.

    Args:
        model_client: The model client to use.

    Returns:
        An AssistantAgent configured for technical analysis.
    """
    return AssistantAgent(
        name="TechnicalAnalystAgent",
        model_client=model_client,
        description="技术分析师，从趋势和动量角度评估投资组合，主张顺势而为、止盈止损。",
        system_message=(
            "你是一位经验丰富的技术分析师，擅长通过收益率趋势和动量信号判断投资时机。\n\n"
            "你的核心观点：\n"
            "1. 趋势是朋友，顺势而为比逆势操作更明智\n"
            "2. 收益率持续上升的产品值得加仓，持续下降的应考虑减仓\n"
            "3. 止盈止损是纪律，不是选择\n\n"
            "你在讨论中的立场：\n"
            "- 支持：加仓近期表现强劲的产品、减仓持续走弱的产品\n"
            "- 反对：长期持有亏损产品、忽视短期趋势变化\n\n"
            "⚠️ 你的发言务必简洁：用3-5句话说明核心判断，列出趋势判断和具体产品建议。\n\n"
            "请用中文回答，观点犀利，数据支撑。"
        ),
    )


def create_risk_controller_agent(model_client: OpenAIChatCompletionClient) -> AssistantAgent:
    """Create the RiskControllerAgent (风险控制官).

    One-vote veto on risk issues. Focuses on risk concentration, drawdown,
    and over-exposure. Argues for diversification, stop-loss, and position limits.

    Args:
        model_client: The model client to use.

    Returns:
        An AssistantAgent configured for risk control.
    """
    return AssistantAgent(
        name="RiskControllerAgent",
        model_client=model_client,
        description="风险控制官，拥有一票否决权，专注于风险集中度、回撤和过度暴露，主张分散投资和仓位控制。",
        system_message=(
            "你是投资组合的风险控制官，你拥有一票否决权——如果任何建议存在不可接受的风险，你可以直接否决。\n\n"
            "你的风险标准：\n"
            "- 单一产品占比超过总资产20%：高风险\n"
            "- 单一类型占比超过总资产40%：集中度风险\n"
            "- 亏损产品持续持有超过180天：机会成本风险\n"
            "- 高风险产品（股票、QDII等）占比超过50%：组合风险过高\n\n"
            "你在讨论中的立场：\n"
            "- 支持：分散投资、设置止损、控制仓位\n"
            "- 反对：任何过度集中的建议\n"
            "- 一票否决：当建议可能导致组合风险超过可接受范围时\n\n"
            "行使否决权时，请在发言中明确使用【否决】标记。\n\n"
            "⚠️ 你的发言务必简洁：用2-3句话说明风险判断，必要时行使否决权。\n\n"
            "请用中文回答，立场坚定。"
        ),
    )


def create_investment_director_agent(model_client: OpenAIChatCompletionClient) -> AssistantAgent:
    """Create the InvestmentDirectorAgent (投资总监).

    Moderates discussion, synthesizes consensus, and produces final
    recommendations. Decides when consensus is reached.

    Args:
        model_client: The model client to use.

    Returns:
        An AssistantAgent configured as the investment director.
    """
    return AssistantAgent(
        name="InvestmentDirectorAgent",
        model_client=model_client,
        description="投资总监，主持圆桌讨论，综合各方意见形成共识决策，产出最终的下周操作建议。",
        system_message=(
            "你是投资总监，负责主持投资研究圆桌会议并做出最终决策。\n\n"
            "其他分析师会给出简短判断，你的任务是综合后输出最终建议。\n\n"
            "当讨论充分后，请按以下简洁格式输出最终决策：\n\n"
            "## 📊 市场判断\n"
            "  - 下周市场方向（一句话）\n"
            "  - 关键驱动因素（利率/政策/指数趋势）\n\n"
            "## 📈 下周操作建议\n"
            "  - 加仓（产品 + 金额 + 原因）\n"
            "  - 减仓/赎回（产品 + 金额 + 原因）\n"
            "  - 持有观望（产品 + 原因）\n\n"
            "## ⚠️ 风险提示\n\n"
            "以 'ROUNDTABLE_COMPLETE' 结束。\n\n"
            "⚠️ 你的输出务必精简：整个报告控制在30行以内，直击要点不要铺垫。\n\n"
            "请用中文回答。"
        ),
    )
