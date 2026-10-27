"""本地 FAISS 索引与检索。

距离使用 faiss.IndexFlatL2。search 返回的是平方 L2 距离，越小越接近。
阈值 max_distance 用同一度量：distance <= max_distance 才算命中。
索引文件由 faiss.write_index / faiss.read_index 读写，不使用 pickle。
"""

import json
import shutil
from enum import Enum
from pathlib import Path

import faiss
import numpy as np
from langchain_core.embeddings import Embeddings
from pydantic import BaseModel

from app.rag.ingest import KnowledgeChunk, read_chunk_catalog, write_chunk_catalog

DEFAULT_INDEX_DIR = Path(__file__).resolve().parents[2] / "data" / "faiss"
_CURRENT_DIR = "current"
_CATALOG_NAME = "chunks.json"
_INDEX_NAME = "index.faiss"
_MANIFEST_NAME = "manifest.json"


class RetrievalStatus(str, Enum):
    HIT = "HIT"
    INSUFFICIENT_EVIDENCE = "INSUFFICIENT_EVIDENCE"
    INDEX_NOT_READY = "INDEX_NOT_READY"
    RETRIEVAL_ERROR = "RETRIEVAL_ERROR"


class RetrievedChunk(BaseModel):
    chunk_id: str
    document_id: str
    title: str
    section: str
    source: str
    content: str
    distance: float


class RetrievalResult(BaseModel):
    status: RetrievalStatus
    hits: list[RetrievedChunk]
    message: str


INDEX_SCHEMA_VERSION = 1


def build_index(
    chunks: list[KnowledgeChunk],
    embeddings: Embeddings,
    index_dir: Path = DEFAULT_INDEX_DIR,
    *,
    embedding_model: str | None = None,
) -> list[KnowledgeChunk]:
    """用当前完整切片重建索引。成功后替换旧索引，失败时保留上一份可用索引。"""
    if len({chunk.chunk_id for chunk in chunks}) != len(chunks):
        raise ValueError("chunk_id 重复，拒绝构建索引")

    staging = index_dir / ".staging"
    live = index_dir / _CURRENT_DIR
    backup = index_dir / ".previous"
    if staging.exists():
        shutil.rmtree(staging)
    staging.mkdir(parents=True)
    try:
        stored = _write_staging(staging, chunks, embeddings, embedding_model=embedding_model)
    except Exception:
        shutil.rmtree(staging, ignore_errors=True)
        raise

    if backup.exists():
        shutil.rmtree(backup)
    try:
        if live.exists():
            live.rename(backup)
        staging.rename(live)
    except Exception:
        if not live.exists() and backup.exists():
            backup.rename(live)
        shutil.rmtree(staging, ignore_errors=True)
        raise
    shutil.rmtree(backup, ignore_errors=True)
    return stored


def retrieve(
    query: str,
    embeddings: Embeddings,
    *,
    index_dir: Path = DEFAULT_INDEX_DIR,
    top_k: int = 3,
    max_distance: float,
    expected_embedding_model: str | None = None,
) -> RetrievalResult:
    """检索已构建的索引。未构建、无命中和执行失败使用不同状态。"""
    if not isinstance(top_k, int) or top_k < 1:
        return _error("top_k 必须是正整数")
    if not isinstance(max_distance, (int, float)):
        return _error("max_distance 必须是数字")

    current = index_dir / _CURRENT_DIR
    catalog_path = current / _CATALOG_NAME
    if not catalog_path.is_file():
        return RetrievalResult(
            status=RetrievalStatus.INDEX_NOT_READY,
            hits=[],
            message="索引尚未构建。",
        )

    try:
        chunks = read_chunk_catalog(catalog_path)
        manifest = _read_manifest(current / _MANIFEST_NAME)
        mismatch = _model_mismatch(manifest, expected_embedding_model)
        if mismatch is not None:
            return mismatch
        if not chunks:
            if manifest.get("count") != 0:
                return _error("空目录与 manifest 不一致")
            return _insufficient()

        index_path = current / _INDEX_NAME
        if not index_path.is_file():
            return _error("向量索引文件缺失")
        index = faiss.read_index(str(index_path))
        if index.metric_type != faiss.METRIC_L2 or index.ntotal != len(chunks):
            return _error("向量索引与切片目录不一致")
        if manifest.get("count") != len(chunks) or manifest.get("metric") != "squared_l2":
            return _error("manifest 与切片目录不一致")

        vector = np.asarray([embeddings.embed_query(query)], dtype=np.float32)
        if vector.shape != (1, index.d):
            return _error("查询向量维度与索引不一致")
        distances, rows = index.search(vector, min(top_k, index.ntotal))
        hits: list[RetrievedChunk] = []
        for distance, row in zip(distances[0], rows[0], strict=True):
            if row < 0 or float(distance) > max_distance:
                continue
            chunk = chunks[int(row)]
            hits.append(
                RetrievedChunk(
                    chunk_id=chunk.chunk_id,
                    document_id=chunk.document_id,
                    title=chunk.title,
                    section=chunk.section,
                    source=chunk.source,
                    content=chunk.content,
                    distance=float(distance),
                )
            )
    except Exception as exc:
        return _error(f"检索失败（{type(exc).__name__}）")

    if not hits:
        return _insufficient()
    return RetrievalResult(
        status=RetrievalStatus.HIT,
        hits=hits,
        message="检索到达到阈值的证据。",
    )


def _write_staging(
    staging: Path,
    chunks: list[KnowledgeChunk],
    embeddings: Embeddings,
    *,
    embedding_model: str | None,
) -> list[KnowledgeChunk]:
    dimension: int | None = None
    if chunks:
        vectors = embeddings.embed_documents([chunk.content for chunk in chunks])
        if len(vectors) != len(chunks):
            raise ValueError("向量数量与切片数量不一致")
        dimension = _dimension(vectors)
        matrix = np.asarray(vectors, dtype=np.float32)
        if matrix.shape != (len(chunks), dimension):
            raise ValueError("向量维度不一致")
        index = faiss.IndexFlatL2(dimension)
        index.add(matrix)
        faiss.write_index(index, str(staging / _INDEX_NAME))
        loaded = faiss.read_index(str(staging / _INDEX_NAME))
        if loaded.ntotal != len(chunks) or loaded.d != dimension:
            raise ValueError("写入后的向量索引与切片不一致")

    stored = write_chunk_catalog(chunks, staging / _CATALOG_NAME)
    if [chunk.chunk_id for chunk in stored] != [chunk.chunk_id for chunk in chunks]:
        raise ValueError("切片目录与本次构建的切片不一致")
    _write_manifest(
        staging / _MANIFEST_NAME,
        count=len(chunks),
        dimension=dimension,
        embedding_model=embedding_model,
    )
    return stored


def _dimension(vectors: list[list[float]]) -> int:
    width = len(vectors[0])
    if width < 1 or any(len(vector) != width for vector in vectors):
        raise ValueError("向量维度不一致")
    return width


def _write_manifest(
    path: Path,
    *,
    count: int,
    dimension: int | None,
    embedding_model: str | None,
) -> None:
    payload = {
        "schema_version": INDEX_SCHEMA_VERSION,
        "metric": "squared_l2",
        "count": count,
        "dimension": dimension,
        "embedding_model": embedding_model,
    }
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _model_mismatch(manifest: dict, expected_embedding_model: str | None) -> RetrievalResult | None:
    if manifest.get("schema_version") != INDEX_SCHEMA_VERSION:
        return _error("索引版本不受支持，需要重建索引")
    if expected_embedding_model is None:
        return None
    if manifest.get("embedding_model") != expected_embedding_model:
        return _error("索引的 Embedding 模型与当前配置不一致，需要使用相同模型重建索引")
    return None


def _read_manifest(path: Path) -> dict:
    if not path.is_file():
        raise ValueError("manifest 缺失")
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("manifest 格式不正确")
    return payload


def _insufficient() -> RetrievalResult:
    return RetrievalResult(
        status=RetrievalStatus.INSUFFICIENT_EVIDENCE,
        hits=[],
        message="检索已执行，无充分依据。",
    )


def _error(message: str) -> RetrievalResult:
    return RetrievalResult(status=RetrievalStatus.RETRIEVAL_ERROR, hits=[], message=message)
