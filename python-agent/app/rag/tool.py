"""把本地检索器暴露给 Agent 的工具。

Embeddings、索引目录、top_k 和 max_distance 由调用方写入 knowledge_search。
导入本模块不会构建索引，也不会请求模型。
"""

from dataclasses import dataclass
from pathlib import Path
from typing import Annotated

from langchain_core.embeddings import Embeddings
from langchain_core.tools import tool
from pydantic import Field

from app.config import settings
from app.rag.embeddings import EmbeddingConfigError, create_ollama_embeddings, embedding_model_id
from app.rag.retriever import DEFAULT_INDEX_DIR, RetrievalResult, RetrievalStatus, retrieve


@dataclass
class KnowledgeSearchSettings:
    embeddings: Embeddings | None = None
    index_dir: Path = DEFAULT_INDEX_DIR
    top_k: int = 3
    max_distance: float | None = None
    embedding_model_id: str | None = None


def _default_model_id() -> str | None:
    provider = settings.embedding_provider.strip()
    model = settings.embedding_model.strip()
    if not provider or not model:
        return None
    return embedding_model_id(provider, model)


knowledge_search = KnowledgeSearchSettings(
    max_distance=settings.embedding_max_distance,
    embedding_model_id=_default_model_id(),
)


@tool
def search_trade_knowledge(
    query: Annotated[str, Field(description="要检索的业务规范问题。")],
) -> str:
    """检索本项目的模拟业务规范，不是真实企业政策。

    用于查询订单状态含义、退款规则，以及发货后未送达时的排查规范。
    不要用它查询某一笔订单的实时状态、交易时间线或支付账户。
    只询问业务规范时，不要因为没有订单号而拒绝检索。
    只有结果为 HIT 且证据足够时，才根据摘录回答。
    INSUFFICIENT_EVIDENCE 表示检索已执行，但没有足够证据。
    INDEX_NOT_READY 表示索引尚未准备好。
    RETRIEVAL_ERROR 表示检索出错，不能当成正常的无命中，也不能解释成业务规则不存在。
    """
    if knowledge_search.embeddings is None and knowledge_search.embedding_model_id is None:
        return _not_ready("Embedding 未配置，无法执行知识检索。")
    if knowledge_search.max_distance is None:
        return _not_ready("max_distance 未配置，无法执行知识检索。")
    try:
        embeddings = _embeddings()
        result = retrieve(
            query,
            embeddings,
            index_dir=knowledge_search.index_dir,
            top_k=knowledge_search.top_k,
            max_distance=knowledge_search.max_distance,
            expected_embedding_model=knowledge_search.embedding_model_id,
        )
    except EmbeddingConfigError:
        return _not_ready("Embedding 未配置，无法执行知识检索。")
    except Exception as exc:
        return _not_ready(f"知识检索失败（{type(exc).__name__}）")
    return format_retrieval(result)


def _embeddings() -> Embeddings:
    if knowledge_search.embeddings is not None:
        return knowledge_search.embeddings
    created = create_ollama_embeddings(
        settings.embedding_provider,
        settings.embedding_model,
        settings.embedding_base_url,
    )
    knowledge_search.embeddings = created
    return created


def format_retrieval(result: RetrievalResult) -> str:
    """把检索状态转成给 Agent 阅读的文本，不把故障写成无命中。"""
    lines = [f"status: {result.status.value}"]
    if result.status is RetrievalStatus.HIT:
        lines.append("这些摘录来自项目模拟业务规范，不是真实企业政策。")
        lines.append("distance_metric: squared_l2（越小越接近，不是相似度分数）")
        for index, hit in enumerate(result.hits, start=1):
            lines.extend(
                [
                    f"[{index}]",
                    f"chunk_id: {hit.chunk_id}",
                    f"document_id: {hit.document_id}",
                    f"title: {hit.title}",
                    f"section: {hit.section}",
                    f"source: {hit.source}",
                    f"squared_l2_distance: {hit.distance}",
                    "content:",
                    hit.content,
                ]
            )
        return "\n".join(lines)
    if result.status is RetrievalStatus.INSUFFICIENT_EVIDENCE:
        lines.append("检索已执行，但无充分依据。")
        return "\n".join(lines)
    if result.status is RetrievalStatus.INDEX_NOT_READY:
        lines.append("索引尚未准备好，无法完成知识检索。")
        return "\n".join(lines)
    lines.append(result.message)
    lines.append("知识检索未能完成。这不是一次正常的无命中。")
    return "\n".join(lines)


def _not_ready(message: str) -> str:
    return "\n".join(
        [
            f"status: {RetrievalStatus.RETRIEVAL_ERROR.value}",
            message,
            "知识检索未能完成。这不是一次正常的无命中。",
        ]
    )
