"""本地 FAISS 检索测试。使用确定性假向量，不调用真实模型。"""

import hashlib
import tempfile
import unittest
from pathlib import Path

import faiss

from app.rag.ingest import KnowledgeChunk, load_knowledge_chunks, read_chunk_catalog
from app.rag.retriever import (
    RetrievalStatus,
    build_index,
    retrieve,
)
from langchain_core.embeddings import Embeddings

_KNOWLEDGE_DIR = Path(__file__).resolve().parents[1] / "knowledge"


class HashEmbeddings(Embeddings):
    def __init__(self, dimension: int = 16):
        self.dimension = dimension

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return [self.embed_query(text) for text in texts]

    def embed_query(self, text: str) -> list[float]:
        digest = hashlib.sha256(text.encode("utf-8")).digest()
        values: list[float] = []
        while len(values) < self.dimension:
            for byte in digest:
                values.append(byte / 255)
                if len(values) == self.dimension:
                    break
        return values


class MappedEmbeddings(Embeddings):
    """按调用方给定的向量表嵌入。未登记的文本会失败，避免悄悄改用别的模型。"""

    def __init__(self, vectors: dict[str, list[float]], dimension: int = 4):
        self.vectors = vectors
        self.dimension = dimension

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return [self.embed_query(text) for text in texts]

    def embed_query(self, text: str) -> list[float]:
        vector = self.vectors[text]
        if len(vector) != self.dimension:
            raise ValueError("向量维度与约定不一致")
        return list(vector)


class BrokenEmbeddings(Embeddings):
    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        raise RuntimeError("embed failed")

    def embed_query(self, text: str) -> list[float]:
        raise RuntimeError("embed failed")


def _chunk(chunk_id: str, content: str, section: str = "章节") -> KnowledgeChunk:
    return KnowledgeChunk(
        document_id="doc",
        chunk_id=chunk_id,
        title="模拟规范",
        section=section,
        source="doc.md",
        content=content,
    )


class RagRetrieverTests(unittest.TestCase):
    def test_fake_embeddings_are_deterministic_and_fixed_width(self):
        embeddings = HashEmbeddings(dimension=16)
        first = embeddings.embed_query("同一段文字")
        second = embeddings.embed_documents(["同一段文字", "另一段文字"])

        self.assertEqual(len(first), 16)
        self.assertEqual(first, second[0])
        self.assertEqual(first, embeddings.embed_query("同一段文字"))
        self.assertNotEqual(first, second[1])

    def test_builds_index_from_phase1_chunks_and_returns_source(self):
        chunks = load_knowledge_chunks(_KNOWLEDGE_DIR)
        target = next(chunk for chunk in chunks if chunk.section == "订单状态定义 / 待处理")
        embeddings = HashEmbeddings()
        with tempfile.TemporaryDirectory() as directory:
            index_dir = Path(directory)
            stored = build_index(chunks, embeddings, index_dir)
            result = retrieve(
                target.content,
                embeddings,
                index_dir=index_dir,
                top_k=2,
                max_distance=0.0,
            )
            catalog = read_chunk_catalog(index_dir / "current" / "chunks.json")
            index = faiss.read_index(str(index_dir / "current" / "index.faiss"))

        self.assertEqual(len(stored), len(chunks))
        self.assertEqual(len(catalog), index.ntotal)
        self.assertEqual(result.status, RetrievalStatus.HIT)
        self.assertLessEqual(len(result.hits), 2)
        hit = result.hits[0]
        self.assertEqual(hit.chunk_id, target.chunk_id)
        self.assertEqual(hit.document_id, target.document_id)
        self.assertEqual(hit.title, "订单状态定义")
        self.assertEqual(hit.section, "订单状态定义 / 待处理")
        self.assertEqual(hit.source, "order-status.md")
        self.assertEqual(hit.content, target.content)
        self.assertEqual(hit.distance, 0.0)

    def test_top_k_limits_hits_and_l2_threshold_keeps_only_near_vectors(self):
        alpha = _chunk("doc:甲", "甲", "甲")
        beta = _chunk("doc:乙", "乙", "乙")
        gamma = _chunk("doc:丙", "丙", "丙")
        embeddings = MappedEmbeddings(
            {
                "甲": [1, 0, 0, 0],
                "乙": [0, 1, 0, 0],
                "丙": [0, 0, 1, 0],
                "靠近甲": [0.8, 0.2, 0, 0],
                "远离": [0, 0, 0, 1],
            }
        )
        with tempfile.TemporaryDirectory() as directory:
            index_dir = Path(directory)
            build_index([alpha, beta, gamma], embeddings, index_dir)
            limited = retrieve("靠近甲", embeddings, index_dir=index_dir, top_k=1, max_distance=2)
            accepted = retrieve("靠近甲", embeddings, index_dir=index_dir, top_k=3, max_distance=0.5)
            rejected = retrieve("远离", embeddings, index_dir=index_dir, top_k=3, max_distance=0.5)

        self.assertEqual(len(limited.hits), 1)
        self.assertEqual(limited.hits[0].chunk_id, "doc:甲")
        self.assertLess(limited.hits[0].distance, 0.2)
        self.assertEqual(accepted.status, RetrievalStatus.HIT)
        self.assertEqual([hit.chunk_id for hit in accepted.hits], ["doc:甲"])
        self.assertEqual(rejected.status, RetrievalStatus.INSUFFICIENT_EVIDENCE)
        self.assertEqual(rejected.hits, [])
        self.assertIn("无充分依据", rejected.message)
        self.assertNotIn("不存在", rejected.message)

    def test_orders_by_ascending_squared_l2_distance(self):
        embeddings = MappedEmbeddings({"甲": [1, 0, 0, 0], "乙": [0, 1, 0, 0], "查询": [1, 0, 0, 0]})
        with tempfile.TemporaryDirectory() as directory:
            index_dir = Path(directory)
            build_index([_chunk("doc:甲", "甲"), _chunk("doc:乙", "乙")], embeddings, index_dir)
            result = retrieve("查询", embeddings, index_dir=index_dir, top_k=2, max_distance=2)

        self.assertEqual([hit.chunk_id for hit in result.hits], ["doc:甲", "doc:乙"])
        self.assertEqual(result.hits[0].distance, 0.0)
        self.assertEqual(result.hits[1].distance, 2.0)

    def test_missing_index_is_not_reported_as_insufficient_evidence(self):
        with tempfile.TemporaryDirectory() as directory:
            result = retrieve(
                "查询",
                HashEmbeddings(),
                index_dir=Path(directory),
                top_k=1,
                max_distance=0.0,
            )

        self.assertEqual(result.status, RetrievalStatus.INDEX_NOT_READY)
        self.assertEqual(result.hits, [])
        self.assertNotIn("无充分依据", result.message)

    def test_retrieval_exception_is_reported(self):
        embeddings = MappedEmbeddings({"甲": [1, 0, 0, 0]})
        with tempfile.TemporaryDirectory() as directory:
            index_dir = Path(directory)
            build_index([_chunk("doc:甲", "甲")], embeddings, index_dir)
            result = retrieve(
                "甲",
                BrokenEmbeddings(),
                index_dir=index_dir,
                top_k=1,
                max_distance=1,
            )

        self.assertEqual(result.status, RetrievalStatus.RETRIEVAL_ERROR)
        self.assertEqual(result.hits, [])
        self.assertIn("RuntimeError", result.message)
        self.assertNotIn("无充分依据", result.message)

    def test_empty_corpus_is_ready_but_has_no_evidence(self):
        with tempfile.TemporaryDirectory() as directory:
            index_dir = Path(directory)
            stored = build_index([], HashEmbeddings(), index_dir)
            result = retrieve(
                "查询",
                HashEmbeddings(),
                index_dir=index_dir,
                top_k=3,
                max_distance=0.0,
            )

        self.assertEqual(stored, [])
        self.assertEqual(result.status, RetrievalStatus.INSUFFICIENT_EVIDENCE)
        self.assertIn("无充分依据", result.message)
        self.assertFalse((index_dir / "current" / "index.faiss").exists())

    def test_rebuild_replaces_previous_chunks(self):
        old = _chunk("doc:旧章节", "旧章节正文", "旧章节")
        kept = _chunk("doc:保留", "保留正文", "保留")
        updated = _chunk("doc:保留", "更新后的正文", "保留")
        added = _chunk("doc:新章节", "新章节正文", "新章节")
        embeddings = HashEmbeddings()
        with tempfile.TemporaryDirectory() as directory:
            index_dir = Path(directory)
            build_index([old, kept], embeddings, index_dir)
            build_index([old, kept], embeddings, index_dir)
            catalog = read_chunk_catalog(index_dir / "current" / "chunks.json")
            self.assertEqual(len(catalog), 2)
            self.assertEqual(len({chunk.chunk_id for chunk in catalog}), 2)

            build_index([updated, added], embeddings, index_dir)
            catalog = read_chunk_catalog(index_dir / "current" / "chunks.json")
            index = faiss.read_index(str(index_dir / "current" / "index.faiss"))
            stale = retrieve(old.content, embeddings, index_dir=index_dir, top_k=2, max_distance=0.0)
            current = retrieve(updated.content, embeddings, index_dir=index_dir, top_k=2, max_distance=0.0)

        self.assertEqual({chunk.chunk_id for chunk in catalog}, {"doc:保留", "doc:新章节"})
        self.assertEqual(index.ntotal, 2)
        self.assertEqual(catalog[0].content, "更新后的正文")
        self.assertEqual(stale.status, RetrievalStatus.INSUFFICIENT_EVIDENCE)
        self.assertEqual(current.hits[0].content, "更新后的正文")
        self.assertEqual(current.hits[0].section, "保留")

    def test_failed_rebuild_keeps_the_previous_index(self):
        chunk = _chunk("doc:甲", "甲")
        embeddings = MappedEmbeddings({"甲": [1, 0, 0, 0]})
        with tempfile.TemporaryDirectory() as directory:
            index_dir = Path(directory)
            build_index([chunk], embeddings, index_dir)
            with self.assertRaises(RuntimeError):
                build_index([chunk], BrokenEmbeddings(), index_dir)
            result = retrieve("甲", embeddings, index_dir=index_dir, top_k=1, max_distance=0.0)

        self.assertEqual(result.status, RetrievalStatus.HIT)
        self.assertEqual(result.hits[0].content, "甲")
        self.assertFalse((index_dir / ".staging").exists())


if __name__ == "__main__":
    unittest.main()
