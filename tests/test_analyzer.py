"""Tests for analyzer module."""

import pytest

from autogen_asset_analyst.analyzer import _build_initial_message


class TestBuildInitialMessage:
    """Tests for _build_initial_message."""

    def test_without_knowledge(self):
        """Builds message without knowledge context."""
        portfolio = "总资产: 100万元\n收益率: 5%"
        result = _build_initial_message(portfolio)
        assert "投资研究圆桌会议" in result
        assert "总资产: 100万元" in result
        assert "价值投资分析师" in result
        assert "个人投资偏好" not in result  # No knowledge section

    def test_with_knowledge(self):
        """Builds message with personal knowledge injected."""
        portfolio = "总资产: 100万元"
        knowledge = "=== 投资人个人知识库 ===\n偏好低风险"
        result = _build_initial_message(portfolio, knowledge)
        assert "投资研究圆桌会议" in result
        assert "总资产: 100万元" in result
        assert "投资人个人知识库" in result
        assert "偏好低风险" in result
        # Knowledge should appear between portfolio data and agent instructions
        assert result.index("总资产") < result.index("个人知识库") < result.index("价值投资分析师")

    def test_knowledge_before_instructions(self):
        """Knowledge context appears before agent instructions."""
        portfolio = "data"
        knowledge = "KNOWLEDGE"
        result = _build_initial_message(portfolio, knowledge)
        pos_knowledge = result.index("KNOWLEDGE")
        pos_value = result.index("价值投资分析师")
        assert pos_knowledge < pos_value

    def test_empty_knowledge(self):
        """Empty knowledge string doesn't add knowledge section."""
        portfolio = "data"
        result = _build_initial_message(portfolio, "")
        assert "投资人个人知识库" not in result
        assert portfolio in result

    def test_contains_all_agent_roles(self):
        """Message mentions all four agent roles."""
        result = _build_initial_message("portfolio")
        assert "价值投资分析师" in result
        assert "技术分析师" in result
        assert "风险控制官" in result
        assert "投资总监" in result
