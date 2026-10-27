"""对照退款三节是否把自身标题放进正文后再嵌入。

不修改生产知识库，不写入 data/faiss/current/。

在 python-agent 目录执行：

    python scripts/compare_refund_title_in_content.py --check
    python scripts/compare_refund_title_in_content.py

A 组嵌入原始 chunk.content。B 组只给三个退款片段的嵌入文本加上该片段自己的标题。
切片上的 title 是文档一级标题，这三节的自身标题取 section 的最后一级。
"""

import argparse
import hashlib
import json
import sys
from pathlib import Path

import faiss

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
SCRIPTS = Path(__file__).resolve().parent
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import compare_embedding_inputs as shared
import evaluate_retrieval
from app.config import settings
from app.rag.embeddings import create_ollama_embeddings, embedding_model_id
from app.rag.ingest import KnowledgeChunk, load_knowledge_chunks, read_chunk_catalog, write_chunk_catalog
from app.rag.retriever import (
    DEFAULT_INDEX_DIR,
    _CATALOG_NAME,
    _CURRENT_DIR,
    _INDEX_NAME,
    _MANIFEST_NAME,
    _write_manifest,
)

OUTPUT = ROOT / "data" / "experiments" / "refund-title-in-content"
PRODUCTION_CURRENT = DEFAULT_INDEX_DIR / _CURRENT_DIR
# section 的最后一级才是该片段自己的标题。title 字段是整篇文档的一级标题。
OWN_HEADINGS = {
    "退款处理规则 / 未发货退款": "未发货退款",
    "退款处理规则 / 已发货但未送达": "已发货但未送达",
    "退款处理规则 / 已送达后退款": "已送达后退款",
}


def embedding_text(chunk: KnowledgeChunk, group: str) -> str:
    if group == "A" or chunk.section not in OWN_HEADINGS:
        return chunk.content
    if group != "B":
        raise ValueError(f"未知实验组：{group}")
    heading = OWN_HEADINGS[chunk.section]
    return f"{heading}\n{chunk.content}"


def run_checks() -> int:
    evaluate_retrieval._validate_cases()
    shared.assert_output_allowed(OUTPUT)
    chunks = load_knowledge_chunks(shared.KNOWLEDGE_DIR)
    targets = [chunk for chunk in chunks if chunk.section in OWN_HEADINGS]
    if len(targets) != 3:
        raise RuntimeError(f"应只找到 3 个退款片段，实际 {len(targets)}")
    if {chunk.section for chunk in targets} != set(OWN_HEADINGS):
        raise RuntimeError("三个退款片段的 section 与预期不一致")
    for chunk in chunks:
        if embedding_text(chunk, "A") != chunk.content:
            raise RuntimeError("A 组嵌入文本不是原始正文")
        group_b = embedding_text(chunk, "B")
        if chunk.section not in OWN_HEADINGS:
            if group_b != chunk.content:
                raise RuntimeError(f"非目标片段的 B 组文本被改动：{chunk.section}")
            continue
        heading = OWN_HEADINGS[chunk.section]
        if chunk.section.split(" / ")[-1] != heading:
            raise RuntimeError("自身标题不是 section 的最后一级")
        if chunk.title == heading:
            raise RuntimeError("生产切片的 title 字段已经是小节标题，实验假设不成立")
        if group_b != f"{heading}\n{chunk.content}":
            raise RuntimeError("B 组没有把自身标题放在原始正文之前")
        if group_b.startswith(f"{chunk.section}\n"):
            raise RuntimeError("B 组使用了完整 section 路径")
        if not group_b.endswith(chunk.content):
            raise RuntimeError("B 组改动了原有正文句子")
    shared._check_metric_reuse(chunks)
    if OUTPUT.exists() and any(OUTPUT.iterdir()):
        raise RuntimeError(
            f"实验目录已有产物：{OUTPUT}\n"
            "不会静默覆盖，也不会写入生产索引。"
        )
    print(f"静态检查通过：切片 {len(chunks)}，退款目标片段 3，评测题 {len(evaluate_retrieval.CASES)}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="对照退款三节是否把自身标题放入正文向量")
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    try:
        if run_checks() != 0:
            return 1
        if args.check:
            return 0
        before = _fingerprint(PRODUCTION_CURRENT)
        report = run_experiment()
        after = _fingerprint(PRODUCTION_CURRENT)
        report["production_index_unchanged"] = before == after
        report["production_index_fingerprint_before"] = before
        report["production_index_fingerprint_after"] = after
        (OUTPUT / "report.json").write_text(
            json.dumps(report, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
    except RuntimeError as exc:
        print(str(exc), file=sys.stderr)
        return 1
    except Exception as exc:
        print(f"对照实验失败（{type(exc).__name__}）", file=sys.stderr)
        return 1
    _print_report(report)
    return 0


def run_experiment() -> dict:
    chunks = load_knowledge_chunks(shared.KNOWLEDGE_DIR)
    model_id = embedding_model_id(settings.embedding_provider, settings.embedding_model)
    embeddings = create_ollama_embeddings(
        settings.embedding_provider,
        settings.embedding_model,
        settings.embedding_base_url,
    )
    texts = {
        "A": [embedding_text(chunk, "A") for chunk in chunks],
        "B": [embedding_text(chunk, "B") for chunk in chunks],
    }
    if texts["A"] == texts["B"]:
        raise RuntimeError("B 组没有改变任何文档向量输入")
    if sum(left != right for left, right in zip(texts["A"], texts["B"], strict=True)) != 3:
        raise RuntimeError("B 组改变的片段数量不是 3")
    document_vectors = {
        group: shared._finite_vectors(embeddings.embed_documents(group_texts), len(chunks))
        for group, group_texts in texts.items()
    }
    query_vectors = [
        shared._finite_vectors([embeddings.embed_query(case["query"])], 1)[0]
        for case in evaluate_retrieval.CASES
    ]
    dimension = len(query_vectors[0])
    for vectors in document_vectors.values():
        if len(vectors[0]) != dimension:
            raise RuntimeError("文档向量与查询向量维度不一致")
    indexes = {group: shared._build_memory_index(vectors) for group, vectors in document_vectors.items()}
    groups = {}
    for group, index in indexes.items():
        hits_by_query = {
            case["query"]: shared._search(index, chunks, query_vectors[offset])
            for offset, case in enumerate(evaluate_retrieval.CASES)
        }
        rows = shared._score_cases(evaluate_retrieval.CASES, hits_by_query)
        groups[group] = shared._summarize(rows)
    _write_indexes(chunks, indexes, document_vectors, model_id, dimension)
    _verify_stored_content(chunks)
    return {
        "embedding_model": model_id,
        "distance_metric": "squared_l2",
        "index_type": "IndexFlatL2",
        "normalization": "不额外归一化，与现有检索一样直接使用 Embedding 返回的向量",
        "query_embedded_once": True,
        "document_inputs": {
            "A": "chunk.content",
            "B": "own heading + newline + chunk.content，仅三个退款片段",
        },
        "b_embedding_texts": {
            chunk.section: embedding_text(chunk, "B")
            for chunk in chunks
            if chunk.section in OWN_HEADINGS
        },
        "stored_content": "chunk.content",
        "chunk_count": len(chunks),
        "dimension": dimension,
        "question_count": len(evaluate_retrieval.CASES),
        "groups": groups,
        "changed_questions": _changed_questions(groups["A"]["cases"], groups["B"]["cases"]),
        "refund_rule_queries": _refund_rule_queries(groups["A"]["cases"], groups["B"]["cases"]),
        "max_distance_calibrated": False,
        "merged_to_production": False,
    }


def _write_indexes(chunks, indexes, document_vectors, model_id: str, dimension: int) -> None:
    for group, index in indexes.items():
        current = OUTPUT / group / _CURRENT_DIR
        current.mkdir(parents=True)
        faiss.write_index(index, str(current / _INDEX_NAME))
        loaded = faiss.read_index(str(current / _INDEX_NAME))
        if loaded.ntotal != len(chunks) or loaded.d != dimension or loaded.metric_type != faiss.METRIC_L2:
            raise RuntimeError(f"{group} 组索引与内存结果不一致")
        stored = write_chunk_catalog(chunks, current / _CATALOG_NAME)
        if [chunk.content for chunk in stored] != [chunk.content for chunk in chunks]:
            raise RuntimeError(f"{group} 组没有保留原始正文")
        if [chunk.section for chunk in stored] != [chunk.section for chunk in chunks]:
            raise RuntimeError(f"{group} 组没有保留 section 元数据")
        _write_manifest(
            current / _MANIFEST_NAME,
            count=len(chunks),
            dimension=len(document_vectors[group][0]),
            embedding_model=model_id,
        )


def _verify_stored_content(chunks: list[KnowledgeChunk]) -> None:
    for group in ("A", "B"):
        stored = read_chunk_catalog(OUTPUT / group / _CURRENT_DIR / _CATALOG_NAME)
        if [(chunk.section, chunk.content) for chunk in stored] != [
            (chunk.section, chunk.content) for chunk in chunks
        ]:
            raise RuntimeError(f"{group} 组保存的正文或 section 与原切片不一致")


def _refund_rule_queries(group_a: list[dict], group_b: list[dict]) -> list[dict]:
    rows = []
    for left, right in zip(group_a, group_b, strict=True):
        if left["expected_section"] not in OWN_HEADINGS:
            continue
        rows.append(
            {
                "query": left["query"],
                "expected_section": left["expected_section"],
                "A": shared._brief(left),
                "B": shared._brief(right),
                "top1_section_changed": _top_section(left) != _top_section(right),
            }
        )
    return rows


def _changed_questions(group_a: list[dict], group_b: list[dict]) -> list[dict]:
    changes = []
    for left, right in zip(group_a, group_b, strict=True):
        if _signature(left) == _signature(right):
            continue
        changes.append(
            {
                "query": left["query"],
                "relevant": left["relevant"],
                "expected_section": left["expected_section"],
                "A_failure_class": left["failure_class"],
                "B_failure_class": right["failure_class"],
                "A_exact_top1_hit": left["exact_top1_hit"],
                "B_exact_top1_hit": right["exact_top1_hit"],
                "A_evidence_top1_hit": left["evidence_top1_hit"],
                "B_evidence_top1_hit": right["evidence_top1_hit"],
                "A_recall_at_3": left["recall_at_3"],
                "B_recall_at_3": right["recall_at_3"],
                "A_hits": left["hits"],
                "B_hits": right["hits"],
            }
        )
    return changes


def _signature(row: dict) -> tuple:
    return (
        row["failure_class"],
        row["exact_top1_hit"],
        row["evidence_top1_hit"],
        row["recall_at_3"],
        row["evidence_in_top3"],
        tuple((hit["section"], hit["chunk_id"], hit["distance"]) for hit in row["hits"]),
    )


def _top_section(row: dict) -> str | None:
    if not row["hits"]:
        return None
    return row["hits"][0]["section"]


def _fingerprint(directory: Path) -> str:
    digest = hashlib.sha256()
    if not directory.exists():
        digest.update(b"missing")
        return digest.hexdigest()
    for path in sorted(item for item in directory.rglob("*") if item.is_file()):
        digest.update(path.relative_to(directory).as_posix().encode())
        digest.update(path.read_bytes())
    return digest.hexdigest()


def _metric_line(group: str, item: dict) -> str:
    return (
        f"{group}：精确 Top-1 {item['exact_top1_hits']}/{item['relevant_count']}，"
        f"精确 Recall@3 {item['recall_at_3']}/{item['relevant_count']}，"
        f"证据 Top-1 {item['evidence_top1_hits']}/{item['relevant_count']}，"
        f"证据 Recall@3 {item['evidence_recall_at_3_hits']}/{item['relevant_count']}"
    )


def _print_report(report: dict) -> None:
    print(f"模型 {report['embedding_model']}，切片 {report['chunk_count']}，维度 {report['dimension']}")
    for group in ("A", "B"):
        item = report["groups"][group]
        print(_metric_line(group, item))
        threshold = next(row for row in item["threshold_comparison"] if row["max_distance"] == 0.75)
        print(f"  {group} 阈值 0.75 无答案误接受 {threshold['unanswerable_false_accepts']}/{item['irrelevant_count']}")
    print(f"结果发生变化的题目：{len(report['changed_questions'])}")
    for change in report["changed_questions"]:
        print(
            f"  {change['query']}："
            f"A {change['A_failure_class']} -> B {change['B_failure_class']}"
        )
    print(f"生产索引未变化：{str(report['production_index_unchanged']).lower()}")
    print("B 没有合并到生产索引。")


if __name__ == "__main__":
    raise SystemExit(main())
