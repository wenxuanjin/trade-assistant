"""知识文档切分测试。不调用模型，也不创建向量。"""

import tempfile
import unittest
from pathlib import Path

from app.rag.ingest import (
    load_knowledge_chunks,
    read_chunk_catalog,
    split_markdown,
    write_chunk_catalog,
)

_KNOWLEDGE_DIR = Path(__file__).resolve().parents[1] / "knowledge"


class KnowledgeIngestTests(unittest.TestCase):
    def test_loads_simulated_trade_documents(self):
        chunks = load_knowledge_chunks(_KNOWLEDGE_DIR)

        by_section = {chunk.section: chunk for chunk in chunks}
        self.assertEqual(
            {chunk.document_id for chunk in chunks},
            {"order-status", "undelivered-after-shipment", "refund-rules"},
        )
        self.assertEqual(len(chunks), len(by_section))
        self.assertIn("模拟业务规范", by_section["订单状态定义"].content)
        self.assertIn("不是真实企业政策", by_section["退款处理规则"].content)

        shipped = by_section["订单状态定义 / 已发货"]
        delivered = by_section["订单状态定义 / 已送达"]
        self.assertEqual(shipped.title, "订单状态定义")
        self.assertEqual(shipped.source, "order-status.md")
        self.assertEqual(shipped.chunk_id, "order-status:订单状态定义 / 已发货")
        self.assertIn("已交给承运方", shipped.content)
        self.assertNotIn("已经收到货", shipped.content)
        self.assertIn("已经收到货", delivered.content)

        moving = by_section["发货后未送达的排查流程 / 按轨迹结果处理 / 轨迹仍在更新"]
        stalled = by_section["发货后未送达的排查流程 / 按轨迹结果处理 / 轨迹长时间无更新"]
        self.assertEqual(moving.document_id, "undelivered-after-shipment")
        self.assertIn("还在运输中", moving.content)
        self.assertNotIn("物流信息停滞", moving.content)
        self.assertIn("物流信息停滞", stalled.content)
        self.assertNotIn("还在运输中", stalled.content)

        in_transit_refund = by_section["退款处理规则 / 已发货但未送达"]
        delivered_refund = by_section["退款处理规则 / 已送达后退款"]
        self.assertNotIn("不再按运输途中丢失处理", in_transit_refund.content)
        self.assertIn("不再按运输途中丢失处理", delivered_refund.content)

    def test_keeps_heading_hierarchy_without_merging_siblings(self):
        chunks = split_markdown(
            "\n".join(
                [
                    "# 发货规则",
                    "总述只属于一级标题。",
                    "## 已发货",
                    "只描述已发货。",
                    "### 运输中",
                    "只描述运输中。",
                    "## 已送达",
                    "只描述已送达。",
                ]
            ),
            document_id="sample",
            source="sample.md",
        )

        sections = [chunk.section for chunk in chunks]
        self.assertEqual(
            sections,
            [
                "发货规则",
                "发货规则 / 已发货",
                "发货规则 / 已发货 / 运输中",
                "发货规则 / 已送达",
            ],
        )
        contents = {chunk.section: chunk.content for chunk in chunks}
        self.assertEqual(contents["发货规则"], "总述只属于一级标题。")
        self.assertEqual(contents["发货规则 / 已发货"], "只描述已发货。")
        self.assertNotIn("只描述已送达。", contents["发货规则 / 已发货 / 运输中"])
        self.assertNotIn("运输中", contents["发货规则 / 已送达"])

    def test_empty_directory_has_no_chunks(self):
        with tempfile.TemporaryDirectory() as directory:
            self.assertEqual(load_knowledge_chunks(Path(directory)), [])

    def test_empty_document_has_no_chunks(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "blank.md").write_text("\n\n  \n", encoding="utf-8")
            (root / "headings-only.md").write_text("# 只有标题\n\n## 没有正文\n", encoding="utf-8")

            self.assertEqual(load_knowledge_chunks(root), [])

    def test_repeated_catalog_write_does_not_duplicate_chunks(self):
        chunks = load_knowledge_chunks(_KNOWLEDGE_DIR)
        with tempfile.TemporaryDirectory() as directory:
            catalog = Path(directory) / "chunks.json"
            first = write_chunk_catalog(chunks, catalog)
            second = write_chunk_catalog(chunks, catalog)
            stored = read_chunk_catalog(catalog)

        self.assertEqual(len(first), len(chunks))
        self.assertEqual([chunk.chunk_id for chunk in second], [chunk.chunk_id for chunk in first])
        self.assertEqual(stored, first)
        self.assertEqual(len({chunk.chunk_id for chunk in stored}), len(stored))
        self.assertEqual(load_knowledge_chunks(_KNOWLEDGE_DIR), chunks)


if __name__ == "__main__":
    unittest.main()
