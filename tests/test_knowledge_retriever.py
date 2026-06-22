"""Tests for knowledge_retriever module."""

import sys
from unittest.mock import Mock, patch

import pytest

from autogen_asset_analyst.knowledge_retriever import (
    _ensure_kb_path,
    format_knowledge_context,
    retrieve_personal_knowledge,
)


class TestEnsureKbPath:
    """Tests for _ensure_kb_path."""

    def test_existing_path(self, tmp_path):
        """Returns resolved Path for existing directory."""
        result = _ensure_kb_path(str(tmp_path))
        assert result is not None
        assert result.is_dir()

    def test_nonexistent_path(self):
        """Returns None for nonexistent directory."""
        result = _ensure_kb_path("/tmp/nonexistent_xyz_12345")
        assert result is None

    def test_file_not_directory(self, tmp_path):
        """Returns Path even for files (code only checks exists())."""
        f = tmp_path / "test.txt"
        f.write_text("data")
        result = _ensure_kb_path(str(f))
        assert result is not None


class TestFormatKnowledgeContext:
    """Tests for format_knowledge_context."""

    def test_empty_dict(self):
        assert format_knowledge_context({}) == ""

    def test_dict_with_empty_lists(self):
        assert format_knowledge_context({"q": []}) == ""

    def test_single_query(self):
        knowledge = {"投资策略": [
            {"content": "偏好低风险", "category": "investment", "source": "g.md"}
        ]}
        result = format_knowledge_context(knowledge)
        assert "投资人个人知识库" in result
        assert "投资策略" in result
        assert "偏好低风险" in result
        assert "请结合以上" in result

    def test_multiple_queries(self):
        knowledge = {
            "投资策略": [{"content": "risk low", "category": "inv", "source": "a.md"}],
            "投资目标": [
                {"content": "retirement", "category": "fin", "source": "b.md"},
                {"content": "house", "category": "fin", "source": "c.md"},
            ],
        }
        result = format_knowledge_context(knowledge)
        assert "risk low" in result
        assert "retirement" in result
        assert "house" in result

    def test_skips_empty_query(self):
        knowledge = {"q1": [{"content": "a", "category": "x", "source": "f.md"}], "q2": []}
        result = format_knowledge_context(knowledge)
        # q1 should appear; q2 shouldn't appear as a section with docs
        assert "q1" in result
        assert "a" in result

    def test_content_truncation(self):
        long_text = "x" * 600
        knowledge = {"q": [{"content": long_text, "category": "c", "source": "f.md"}]}
        result = format_knowledge_context(knowledge)
        assert "x" * 300 in result
        assert "x" * 301 not in result


class TestRetrievePersonalKnowledge:
    """Tests for retrieve_personal_knowledge."""

    def test_path_not_found(self):
        result = retrieve_personal_knowledge("/nonexistent/path")
        assert result == {}

    def test_import_error(self, tmp_path):
        """Returns empty dict when import fails on temp path."""
        with patch("autogen_asset_analyst.knowledge_retriever._ensure_kb_path") as mock_ensure:
            mock_ensure.return_value = tmp_path
            result = retrieve_personal_knowledge(str(tmp_path))
            assert result == {}

    def test_successful_retrieval(self, tmp_path):
        """Test with mocked RAG system."""
        from langchain_core.documents import Document

        mock_rag = Mock()
        mock_rag.retrieve_documents.return_value = [
            Document(page_content="偏好低风险", metadata={"category": "investment", "source": "g.md"}),
            Document(page_content="年化目标5-8%", metadata={"category": "financial", "source": "h.md"}),
        ]

        # Mock RAGSystem constructor
        mock_rag_cls = Mock(return_value=mock_rag)

        # Pre-register langchain_llm_toolkit.rag in sys.modules so the import works
        fake_rag_module = Mock()
        fake_rag_module.RAGSystem = mock_rag_cls
        sys.modules["langchain_llm_toolkit"] = Mock()
        sys.modules["langchain_llm_toolkit.rag"] = fake_rag_module

        try:
            with patch("autogen_asset_analyst.knowledge_retriever._ensure_kb_path") as mock_ensure:
                mock_ensure.return_value = tmp_path

                knowledge = retrieve_personal_knowledge(
                    str(tmp_path),
                    queries=["投资策略"],
                )
        finally:
            sys.modules.pop("langchain_llm_toolkit.rag", None)
            sys.modules.pop("langchain_llm_toolkit", None)

        assert len(knowledge) == 1
        docs = knowledge["投资策略"]
        assert len(docs) == 2
        assert docs[0]["content"] == "偏好低风险"
        assert docs[1]["content"] == "年化目标5-8%"

    def test_retrieval_with_default_queries(self, tmp_path):
        """Uses three default queries when none provided."""
        mock_rag = Mock()
        mock_rag.retrieve_documents.return_value = []
        mock_rag_cls = Mock(return_value=mock_rag)

        fake_rag_module = Mock()
        fake_rag_module.RAGSystem = mock_rag_cls
        sys.modules["langchain_llm_toolkit"] = Mock()
        sys.modules["langchain_llm_toolkit.rag"] = fake_rag_module

        try:
            with patch("autogen_asset_analyst.knowledge_retriever._ensure_kb_path") as mock_ensure:
                mock_ensure.return_value = tmp_path
                knowledge = retrieve_personal_knowledge(str(tmp_path))
        finally:
            sys.modules.pop("langchain_llm_toolkit.rag", None)
            sys.modules.pop("langchain_llm_toolkit", None)

        assert len(knowledge) == 3  # 3 default queries

    def test_query_failure_handled(self, tmp_path):
        """Handles partial query failures gracefully."""
        from langchain_core.documents import Document

        mock_rag = Mock()
        mock_rag.retrieve_documents.side_effect = [
            [Document(page_content="ok", metadata={})],
            RuntimeError("query failed"),
            [Document(page_content="ok2", metadata={})],
        ]
        mock_rag_cls = Mock(return_value=mock_rag)

        fake_rag_module = Mock()
        fake_rag_module.RAGSystem = mock_rag_cls
        sys.modules["langchain_llm_toolkit"] = Mock()
        sys.modules["langchain_llm_toolkit.rag"] = fake_rag_module

        try:
            with patch("autogen_asset_analyst.knowledge_retriever._ensure_kb_path") as mock_ensure:
                mock_ensure.return_value = tmp_path
                knowledge = retrieve_personal_knowledge(
                    str(tmp_path), queries=["q1", "q2", "q3"]
                )
        finally:
            sys.modules.pop("langchain_llm_toolkit.rag", None)
            sys.modules.pop("langchain_llm_toolkit", None)

        assert len(knowledge["q1"]) == 1
        assert len(knowledge["q2"]) == 0
        assert len(knowledge["q3"]) == 1

    def test_load_vector_store_failure(self, tmp_path):
        """Returns empty dict when RAGSystem init fails."""
        mock_rag_cls = Mock(side_effect=RuntimeError("load failed"))

        fake_rag_module = Mock()
        fake_rag_module.RAGSystem = mock_rag_cls
        sys.modules["langchain_llm_toolkit"] = Mock()
        sys.modules["langchain_llm_toolkit.rag"] = fake_rag_module

        try:
            with patch("autogen_asset_analyst.knowledge_retriever._ensure_kb_path") as mock_ensure:
                mock_ensure.return_value = tmp_path
                knowledge = retrieve_personal_knowledge(str(tmp_path))
        finally:
            sys.modules.pop("langchain_llm_toolkit.rag", None)
            sys.modules.pop("langchain_llm_toolkit", None)

        assert knowledge == {}
