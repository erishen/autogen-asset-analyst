"""Knowledge base retriever for personal investment preferences.

Queries the langchain-llm-toolkit RAG system to retrieve the user's
personal knowledge, investment preferences, and strategy context
before running investment analysis.
"""

from __future__ import annotations

import logging
import sys
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


def _ensure_kb_path(kb_path: str) -> Path:
    """Validate and resolve the knowledge base path."""
    path = Path(kb_path).resolve()
    if not path.exists():
        logger.warning("Knowledge base path not found: %s, skipping", path)
        return None
    return path


def retrieve_personal_knowledge(
    kb_path: str,
    queries: list[str] | None = None,
) -> dict[str, list[dict[str, Any]]]:
    """Retrieve personal investment knowledge from the RAG system.

    Args:
        kb_path: Path to the langchain-llm-toolkit project.
        queries: List of queries to retrieve. Defaults to investment-related queries.

    Returns:
        Dict mapping query -> list of retrieved document dicts.
    """
    kb_dir = _ensure_kb_path(kb_path)
    if kb_dir is None:
        return {}

    if queries is None:
        queries = [
            "投资策略 投资偏好 风险偏好",
            "个人投资经验 资产配置",
            "投资目标 收益预期",
        ]

    # Add kb_path to sys.path so we can import rag module
    sys.path.insert(0, str(kb_dir / "src"))

    try:
        from langchain_llm_toolkit.rag import RAGSystem
    except ImportError:
        logger.warning("Cannot import langchain_llm_toolkit.rag, skipping knowledge retrieval")
        sys.path.pop(0)
        return {}

    try:
        rag = RAGSystem(
            vector_store_type="faiss",
            embedding_type="ollama",
            embedding_model="nomic-embed-text:latest",
        )
        # Use absolute path for vector store
        rag.vector_store_dir = str(kb_dir / "vector_store")
        rag.faiss_persist_dir = str(kb_dir / "vector_store")
        rag.load_vector_store()

        results: dict[str, list[dict[str, Any]]] = {}
        for query in queries:
            try:
                docs = rag.retrieve_hybrid(query, k=3, bm25_weight=0.3)
                results[query] = [
                    {
                        "content": doc.page_content[:500],
                        "category": doc.metadata.get("category", "unknown"),
                        "source": doc.metadata.get("source", "unknown"),
                    }
                    for doc in docs
                ]
            except Exception as e:
                logger.warning("Failed to query '%s': %s", query, e)
                results[query] = []

        logger.info(
            "Retrieved personal knowledge for %d queries, %d total docs",
            len(queries),
            sum(len(v) for v in results.values()),
        )
        return results

    except Exception as e:
        logger.warning("Failed to load vector store: %s", e)
        return {}
    finally:
        sys.path.pop(0)


def format_knowledge_context(knowledge: dict[str, list[dict[str, Any]]]) -> str:
    """Format retrieved knowledge into a readable context string.

    Args:
        knowledge: Dict mapping queries to document lists.

    Returns:
        Formatted string for inclusion in the analysis context.
    """
    if not knowledge:
        return ""

    total_docs = sum(len(v) for v in knowledge.values())
    if total_docs == 0:
        return ""

    lines = [
        "=== 投资人个人知识库（投资偏好、策略经验） ===",
        "",
    ]

    for query, docs in knowledge.items():
        if not docs:
            continue
        lines.append(f"关于「{query}」的相关知识：")
        for i, doc in enumerate(docs, 1):
            lines.append(f"  [{doc['category']}] {doc['content'][:300]}")
        lines.append("")

    lines.append("请结合以上个人投资偏好和知识进行分析。")
    return "\n".join(lines)
