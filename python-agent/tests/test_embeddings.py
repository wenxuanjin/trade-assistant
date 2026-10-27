"""Embedding 配置与索引模型标识测试。不连接 Ollama。"""

import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from app.config import Settings
from app.rag.embeddings import EmbeddingConfigError, create_ollama_embeddings, embedding_model_id
from app.rag.ingest import load_knowledge_chunks
from app.rag.retriever import RetrievalStatus, build_index, retrieve
from app.rag.tool import knowledge_search, search_trade_knowledge
from tests.test_agent_behavior import _configured_knowledge_search
from tests.test_rag_retriever import HashEmbeddings

_KNOWLEDGE_DIR = Path(__file__).resolve().parents[1] / "knowledge"


class EmbeddingSettingsTests(unittest.TestCase):
    def test_embedding_settings_do_not_reuse_the_chat_model(self):
        with patch.dict(os.environ, {}, clear=True):
            loaded = Settings(
                _env_file=None,
                openai_api_key="sk-unit-test-only",
                openai_base_url="https://api.deepseek.com",
                openai_model="deepseek-v4-flash",
            )

        self.assertEqual(loaded.embedding_provider, "ollama")
        self.assertEqual(loaded.embedding_model, "bge-m3")
        self.assertEqual(loaded.embedding_base_url, "http://localhost:11434")
        self.assertIsNone(loaded.embedding_max_distance)
        self.assertNotEqual(loaded.embedding_base_url, loaded.openai_base_url)
        self.assertNotEqual(loaded.embedding_model, loaded.openai_model)
        self.assertNotIn("sk-unit-test-only", loaded.embedding_base_url)
        self.assertNotIn("sk-unit-test-only", loaded.embedding_model)

    def test_blank_embedding_config_is_rejected(self):
        with self.assertRaises(EmbeddingConfigError) as raised:
            create_ollama_embeddings(" ", "", "http://localhost:11434")
        self.assertIn("Embedding 未配置", str(raised.exception))
        self.assertNotIn("sk-", str(raised.exception))

    def test_unknown_provider_is_rejected(self):
        with self.assertRaises(EmbeddingConfigError) as raised:
            create_ollama_embeddings("deepseek", "deepseek-v4-flash", "https://api.deepseek.com")
        self.assertIn("不支持的 Embedding 提供方", str(raised.exception))
        self.assertNotIn("sk-", str(raised.exception))

    def test_client_is_created_without_calling_the_service(self):
        with patch("httpx.Client.send", side_effect=AssertionError("不应在创建时访问网络")):
            client = create_ollama_embeddings("ollama", "bge-m3", "http://localhost:11434/")
        self.assertEqual(client.model, "bge-m3")
        self.assertEqual(str(client.base_url).rstrip("/"), "http://localhost:11434")
        self.assertEqual(client.client_kwargs.get("trust_env"), False)
        self.assertEqual(embedding_model_id("ollama", "bge-m3"), "ollama/bge-m3")


class EmbeddingIndexTests(unittest.TestCase):
    def test_build_and_query_keep_the_same_embedding_model(self):
        chunks = load_knowledge_chunks(_KNOWLEDGE_DIR)
        target = next(chunk for chunk in chunks if chunk.section == "订单状态定义 / 待处理")
        embeddings = HashEmbeddings()
        model_id = "ollama/bge-m3"
        with tempfile.TemporaryDirectory() as directory:
            index_dir = Path(directory)
            build_index(chunks, embeddings, index_dir, embedding_model=model_id)
            result = retrieve(
                target.content,
                embeddings,
                index_dir=index_dir,
                max_distance=0.0,
                expected_embedding_model=model_id,
            )
        self.assertIs(result.status, RetrievalStatus.HIT)
        self.assertEqual(result.hits[0].section, "订单状态定义 / 待处理")

    def test_different_embedding_model_is_rejected(self):
        chunks = load_knowledge_chunks(_KNOWLEDGE_DIR)
        embeddings = HashEmbeddings()
        with tempfile.TemporaryDirectory() as directory:
            index_dir = Path(directory)
            build_index(chunks, embeddings, index_dir, embedding_model="ollama/bge-m3")
            result = retrieve(
                "待处理是什么意思",
                embeddings,
                index_dir=index_dir,
                max_distance=0.0,
                expected_embedding_model="ollama/other-model",
            )
        self.assertIs(result.status, RetrievalStatus.RETRIEVAL_ERROR)
        self.assertIn("模型与当前配置不一致", result.message)
        self.assertNotIn("无充分依据", result.message)

    def test_ollama_connection_failure_is_not_a_miss(self):
        with tempfile.TemporaryDirectory() as directory:
            with _configured_knowledge_search(
                None,
                Path(directory),
                max_distance=1.0,
                embedding_model_id="ollama/bge-m3",
            ):
                with patch(
                    "app.rag.tool.create_ollama_embeddings",
                    side_effect=ConnectionError("down"),
                ):
                    text = search_trade_knowledge.invoke({"query": "待处理是什么意思"})
        self.assertIn("status: RETRIEVAL_ERROR", text)
        self.assertIn("ConnectionError", text)
        self.assertIn("这不是一次正常的无命中", text)
        self.assertNotIn("无充分依据", text)
        self.assertNotIn("down", text)
        self.assertIsNone(knowledge_search.embeddings)
