"""对照两种文档 Embedding 输入。不写入生产索引，也不修改评测标注。

在 python-agent 目录执行：

    python scripts/compare_embedding_inputs.py --check
    python scripts/compare_embedding_inputs.py

A 组只嵌入 chunk.content。B 组嵌入 chunk.section、换行和 chunk.content。
查询向量每条只生成一次，供两组索引共用。若默认实验目录已有产物，请改用
--output data/experiments/<新目录名>。
"""

import argparse
import json
import math
import sys
from pathlib import Path

import faiss
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
SCRIPTS = Path(__file__).resolve().parent
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import evaluate_retrieval
from app.config import settings
from app.rag.embeddings import create_ollama_embeddings, embedding_model_id
from app.rag.ingest import KnowledgeChunk, load_knowledge_chunks, read_chunk_catalog, write_chunk_catalog
from app.rag.retriever import (
    DEFAULT_INDEX_DIR,
    RetrievalResult,
    RetrievalStatus,
    RetrievedChunk,
    _CATALOG_NAME,
    _CURRENT_DIR,
    _INDEX_NAME,
    _MANIFEST_NAME,
    _write_manifest,
)

EXPERIMENTS_ROOT = ROOT / "data" / "experiments"
DEFAULT_OUTPUT = EXPERIMENTS_ROOT / "section-plus-content"
KNOWLEDGE_DIR = ROOT / "knowledge"
BASELINE_REPORT = ROOT / "data" / "retrieval-eval" / "report.json"
STATED_BASELINE = {
    "exact_top1_hits": 21,
    "recall_at_3": 23,
    "evidence_top1_hits": 22,
    "evidence_recall_at_3_hits": 23,
    "relevant_count": 23,
    "false_accepts_at_0_75": 0,
    "irrelevant_count": 4,
}


def document_text(chunk: KnowledgeChunk, group: str) -> str:
    """A 只用正文。B 在正文前加上已有章节路径。查询和评测标签不进入文档向量。"""
    if group == "A":
        return chunk.content
    if group == "B":
        return f"{chunk.section}\n{chunk.content}"
    raise ValueError(f"未知实验组：{group}")


def resolve_output(path: Path) -> Path:
    if not path.is_absolute():
        path = ROOT / path
    return path.resolve()


def assert_output_allowed(path: Path) -> None:
    resolved = path.resolve()
    experiments = EXPERIMENTS_ROOT.resolve()
    production = DEFAULT_INDEX_DIR.resolve()
    if experiments not in resolved.parents:
        raise RuntimeError(
            "实验目录必须位于 python-agent/data/experiments/ 下的子目录。"
            "请使用 --output data/experiments/<新目录名>。"
        )
    if resolved == production or production in resolved.parents:
        raise RuntimeError("拒绝写入生产索引 python-agent/data/faiss/。")
    current = (DEFAULT_INDEX_DIR / _CURRENT_DIR).resolve()
    if resolved == current or current in resolved.parents:
        raise RuntimeError("拒绝写入或覆盖 python-agent/data/faiss/current/。")


def assert_output_empty(path: Path) -> None:
    if path.exists() and any(path.iterdir()):
        raise RuntimeError(
            f"实验目录已有产物：{path}\n"
            "不会静默覆盖。请换一个新目录，例如：\n"
            "python scripts/compare_embedding_inputs.py --output data/experiments/section-plus-content-2"
        )


def run_checks(output: Path) -> int:
    evaluate_retrieval._validate_cases()
    assert_output_allowed(output)
    for forbidden in (DEFAULT_INDEX_DIR, DEFAULT_INDEX_DIR / _CURRENT_DIR, ROOT / "data" / "faiss"):
        try:
            assert_output_allowed(forbidden)
        except RuntimeError:
            continue
        raise RuntimeError(f"路径隔离失效，未拒绝：{forbidden}")
    chunks = load_knowledge_chunks(KNOWLEDGE_DIR)
    if not chunks:
        raise RuntimeError("知识切片为空")
    for chunk in chunks:
        group_a = document_text(chunk, "A")
        group_b = document_text(chunk, "B")
        if group_a != chunk.content:
            raise RuntimeError("A 组文档向量输入不是原始正文")
        if group_b != f"{chunk.section}\n{chunk.content}":
            raise RuntimeError("B 组文档向量输入不是章节路径、换行和原始正文")
        if not group_b.startswith(f"{chunk.section}\n"):
            raise RuntimeError("B 组没有使用切片上的 section 字段")
    if evaluate_retrieval.CANDIDATE_THRESHOLDS != (0.25, 0.5, 0.75, 1.0, 1.25, 1.5, 2.0):
        raise RuntimeError("候选阈值与现有评测脚本不一致")
    _check_metric_reuse(chunks)
    try:
        assert_output_empty(output)
    except RuntimeError as exc:
        print(str(exc), file=sys.stderr)
        return 1
    print(
        f"静态检查通过：切片 {len(chunks)}，评测题 {len(evaluate_retrieval.CASES)}，"
        f"实验目录可写 {output}"
    )
    return 0


def _check_metric_reuse(chunks: list[KnowledgeChunk]) -> None:
    case = next(item for item in evaluate_retrieval.CASES if item["query"] == "货已经送达之后怎么处理退款")
    matched = next(chunk for chunk in chunks if chunk.section == case["section"])
    hit = _retrieved(matched, 0.1)
    exact = _score_cases([case], {case["query"]: [hit]})[0]
    if not exact["exact_top1_hit"] or not exact["evidence_top1_hit"]:
        raise RuntimeError("未能复用现有精确命中和证据命中计算")
    wrong = hit.model_copy(update={"section": "退款处理规则 / 已发货但未送达", "chunk_id": "check"})
    missed = _score_cases([case], {case["query"]: [wrong]})[0]
    if missed["exact_top1_hit"] or missed["evidence_top1_hit"] or missed["recall_at_3"]:
        raise RuntimeError("现有评测规则没有按原样拒绝错误章节")


def main() -> int:
    parser = argparse.ArgumentParser(description="对照 content 与 section+content 的文档向量")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--check", action="store_true", help="只做路径、输入文本和指标复用检查")
    args = parser.parse_args()
    output = resolve_output(args.output)
    if args.check:
        try:
            return run_checks(output)
        except RuntimeError as exc:
            print(str(exc), file=sys.stderr)
            return 1
    try:
        if run_checks(output) != 0:
            return 1
        report = run_experiment(output)
    except RuntimeError as exc:
        print(str(exc), file=sys.stderr)
        return 1
    except Exception as exc:
        print(f"对照实验失败（{type(exc).__name__}）", file=sys.stderr)
        return 1
    _print_report(report)
    return 0


def run_experiment(output: Path) -> dict:
    chunks = load_knowledge_chunks(KNOWLEDGE_DIR)
    model_id = embedding_model_id(settings.embedding_provider, settings.embedding_model)
    embeddings = create_ollama_embeddings(
        settings.embedding_provider,
        settings.embedding_model,
        settings.embedding_base_url,
    )
    texts = {
        "A": [document_text(chunk, "A") for chunk in chunks],
        "B": [document_text(chunk, "B") for chunk in chunks],
    }
    document_vectors = {
        group: _finite_vectors(embeddings.embed_documents(group_texts), len(chunks))
        for group, group_texts in texts.items()
    }
    query_vectors = [
        _finite_vectors([embeddings.embed_query(case["query"])], 1)[0]
        for case in evaluate_retrieval.CASES
    ]
    dimension = len(query_vectors[0])
    for group, vectors in document_vectors.items():
        if len(vectors[0]) != dimension:
            raise RuntimeError(f"{group} 组文档向量与查询向量维度不一致")
    indexes = {group: _build_memory_index(vectors) for group, vectors in document_vectors.items()}
    groups = {}
    for group, index in indexes.items():
        hits_by_query = {
            case["query"]: _search(index, chunks, query_vectors[offset])
            for offset, case in enumerate(evaluate_retrieval.CASES)
        }
        rows = _score_cases(evaluate_retrieval.CASES, hits_by_query)
        groups[group] = _summarize(rows)
    _write_outputs(output, chunks, indexes, document_vectors, model_id, dimension)
    _verify_stored_content(output, chunks)
    report = {
        "embedding_model": model_id,
        "distance_metric": "squared_l2",
        "index_type": "IndexFlatL2",
        "normalization": "不额外归一化，与现有检索一样直接使用 Embedding 返回的向量",
        "query_embedded_once": True,
        "document_inputs": {
            "A": "chunk.content",
            "B": "chunk.section + newline + chunk.content",
        },
        "stored_content": "chunk.content",
        "chunk_count": len(chunks),
        "dimension": dimension,
        "question_count": len(evaluate_retrieval.CASES),
        "groups": groups,
        "top1_changes": _top1_changes(groups["A"]["cases"], groups["B"]["cases"]),
        "refund_questions": _refund_comparison(groups["A"]["cases"], groups["B"]["cases"]),
        "baseline_comparison": _baseline_comparison(groups["A"]),
        "max_distance_calibrated": False,
        "conclusion_limit": "这是 27 条样本上的一次对照，不能当成普遍有效的结论，也没有写入生产配置。",
    }
    report_path = output / "report.json"
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return report


def _finite_vectors(raw: list[list[float]], expected_count: int) -> list[list[float]]:
    if len(raw) != expected_count:
        raise RuntimeError("向量数量与输入数量不一致")
    vectors: list[list[float]] = []
    for vector in raw:
        if not vector:
            raise RuntimeError("向量为空")
        numbers = [float(value) for value in vector]
        if any(not math.isfinite(number) for number in numbers):
            raise RuntimeError("向量含有非有限数值")
        vectors.append(numbers)
    width = len(vectors[0])
    if any(len(vector) != width for vector in vectors):
        raise RuntimeError("向量维度不一致")
    return vectors


def _build_memory_index(vectors: list[list[float]]) -> faiss.Index:
    matrix = np.asarray(vectors, dtype=np.float32)
    index = faiss.IndexFlatL2(matrix.shape[1])
    index.add(matrix)
    if index.metric_type != faiss.METRIC_L2 or index.ntotal != len(vectors):
        raise RuntimeError("内存索引与切片数量不一致")
    return index


def _search(index: faiss.Index, chunks: list[KnowledgeChunk], query_vector: list[float]) -> list[RetrievedChunk]:
    vector = np.asarray([query_vector], dtype=np.float32)
    distances, rows = index.search(vector, min(3, index.ntotal))
    hits: list[RetrievedChunk] = []
    for distance, row in zip(distances[0], rows[0], strict=True):
        if int(row) < 0:
            continue
        chunk = chunks[int(row)]
        hits.append(_retrieved(chunk, float(distance)))
    return hits


def _retrieved(chunk: KnowledgeChunk, distance: float) -> RetrievedChunk:
    return RetrievedChunk(
        chunk_id=chunk.chunk_id,
        document_id=chunk.document_id,
        title=chunk.title,
        section=chunk.section,
        source=chunk.source,
        content=chunk.content,
        distance=distance,
    )


def _score_cases(cases: list[dict], hits_by_query: dict[str, list[RetrievedChunk]]) -> list[dict]:
    def fake_retrieve(query: str, embeddings, **kwargs) -> RetrievalResult:
        del embeddings, kwargs
        found = hits_by_query[query]
        if found:
            return RetrievalResult(status=RetrievalStatus.HIT, hits=found, message="检索到达到阈值的证据。")
        return RetrievalResult(
            status=RetrievalStatus.INSUFFICIENT_EVIDENCE,
            hits=[],
            message="检索已执行，无充分依据。",
        )

    original = evaluate_retrieval.retrieve
    evaluate_retrieval.retrieve = fake_retrieve
    try:
        return [evaluate_retrieval._evaluate_case(case, None, "experiment") for case in cases]
    finally:
        evaluate_retrieval.retrieve = original


def _summarize(rows: list[dict]) -> dict:
    relevant = [row for row in rows if row["relevant"]]
    irrelevant = [row for row in rows if not row["relevant"]]
    relevant_count = len(relevant)
    exact_top1_hits = sum(row["exact_top1_hit"] for row in relevant)
    evidence_top1_hits = sum(row["evidence_top1_hit"] for row in relevant)
    exact_recall_at_3 = sum(row["recall_at_3"] for row in relevant)
    evidence_recall_at_3_hits = sum(row["evidence_in_top3"] for row in relevant)
    return {
        "relevant_count": relevant_count,
        "irrelevant_count": len(irrelevant),
        "exact_top1_hits": exact_top1_hits,
        "exact_top1_accuracy": exact_top1_hits / relevant_count,
        "recall_at_3": exact_recall_at_3,
        "recall_at_3_rate": exact_recall_at_3 / relevant_count,
        "evidence_top1_hits": evidence_top1_hits,
        "evidence_top1_accuracy": evidence_top1_hits / relevant_count,
        "evidence_recall_at_3_hits": evidence_recall_at_3_hits,
        "evidence_recall_at_3": evidence_recall_at_3_hits / relevant_count,
        "evidence_metric_note": evaluate_retrieval.EVIDENCE_METRIC_NOTE,
        "threshold_comparison": evaluate_retrieval._threshold_report(relevant, irrelevant),
        "cases": rows,
    }


def _write_outputs(
    output: Path,
    chunks: list[KnowledgeChunk],
    indexes: dict[str, faiss.Index],
    document_vectors: dict[str, list[list[float]]],
    model_id: str,
    dimension: int,
) -> None:
    assert_output_empty(output)
    for group, index in indexes.items():
        current = output / group / _CURRENT_DIR
        current.mkdir(parents=True)
        faiss.write_index(index, str(current / _INDEX_NAME))
        loaded = faiss.read_index(str(current / _INDEX_NAME))
        if loaded.ntotal != len(chunks) or loaded.d != dimension or loaded.metric_type != faiss.METRIC_L2:
            raise RuntimeError(f"{group} 组写入后的索引与内存索引不一致")
        stored = write_chunk_catalog(chunks, current / _CATALOG_NAME)
        if [chunk.content for chunk in stored] != [chunk.content for chunk in chunks]:
            raise RuntimeError(f"{group} 组切片目录没有保留原始正文")
        _write_manifest(
            current / _MANIFEST_NAME,
            count=len(chunks),
            dimension=len(document_vectors[group][0]),
            embedding_model=model_id,
        )


def _verify_stored_content(output: Path, chunks: list[KnowledgeChunk]) -> None:
    original = [chunk.content for chunk in chunks]
    for group in ("A", "B"):
        stored = read_chunk_catalog(output / group / _CURRENT_DIR / _CATALOG_NAME)
        if [chunk.content for chunk in stored] != original:
            raise RuntimeError(f"{group} 组返回的正文不是原始 chunk.content")
        if [chunk.section for chunk in stored] != [chunk.section for chunk in chunks]:
            raise RuntimeError(f"{group} 组章节路径与原切片不一致")


def _top1_changes(group_a: list[dict], group_b: list[dict]) -> list[dict]:
    paired = zip(group_a, group_b, strict=True)
    changes = []
    for left, right in paired:
        left_top = left["hits"][0]["section"] if left["hits"] else None
        right_top = right["hits"][0]["section"] if right["hits"] else None
        if left_top == right_top:
            continue
        changes.append(
            {
                "query": left["query"],
                "expected_section": left["expected_section"],
                "A_top1": left_top,
                "B_top1": right_top,
                "A_failure_class": left["failure_class"],
                "B_failure_class": right["failure_class"],
                "A_exact_top1_hit": left["exact_top1_hit"],
                "B_exact_top1_hit": right["exact_top1_hit"],
                "A_evidence_top1_hit": left["evidence_top1_hit"],
                "B_evidence_top1_hit": right["evidence_top1_hit"],
            }
        )
    return changes


def _refund_comparison(group_a: list[dict], group_b: list[dict]) -> list[dict]:
    rows = []
    for left, right in zip(group_a, group_b, strict=True):
        if "退款" not in left["query"]:
            continue
        rows.append(
            {
                "query": left["query"],
                "expected_section": left["expected_section"],
                "A": _brief(left),
                "B": _brief(right),
            }
        )
    return rows


def _brief(row: dict) -> dict:
    return {
        "failure_class": row["failure_class"],
        "exact_top1_hit": row["exact_top1_hit"],
        "evidence_top1_hit": row["evidence_top1_hit"],
        "recall_at_3": row["recall_at_3"],
        "evidence_in_top3": row["evidence_in_top3"],
        "hits": row["hits"],
    }


def _baseline_comparison(group_a: dict) -> dict:
    threshold = next(item for item in group_a["threshold_comparison"] if item["max_distance"] == 0.75)
    labels_match = (
        group_a["exact_top1_hits"] == STATED_BASELINE["exact_top1_hits"]
        and group_a["recall_at_3"] == STATED_BASELINE["recall_at_3"]
        and group_a["evidence_top1_hits"] == STATED_BASELINE["evidence_top1_hits"]
        and group_a["evidence_recall_at_3_hits"] == STATED_BASELINE["evidence_recall_at_3_hits"]
        and threshold["unanswerable_false_accepts"] == STATED_BASELINE["false_accepts_at_0_75"]
    )
    saved = _saved_report_comparison(group_a["cases"])
    return {
        "stated_baseline": STATED_BASELINE,
        "A_label_metrics_match_stated_baseline": labels_match,
        "saved_production_report": saved,
        "note": "A 组是本次重新嵌入的 content 对照，不是上一份生产报告的原距离。",
    }


def _saved_report_comparison(cases: list[dict]) -> dict:
    if not BASELINE_REPORT.is_file():
        return {"available": False}
    saved = json.loads(BASELINE_REPORT.read_text(encoding="utf-8"))
    saved_cases = {row["query"]: row for row in saved["cases"]}
    mismatches = []
    for row in cases:
        previous = saved_cases.get(row["query"])
        if previous is None:
            mismatches.append({"query": row["query"], "reason": "历史报告没有这道题"})
            continue
        previous_top = previous["hits"][0]["section"] if previous["hits"] else None
        current_top = row["hits"][0]["section"] if row["hits"] else None
        if (
            previous.get("exact_top1_hit") != row["exact_top1_hit"]
            or previous.get("evidence_top1_hit") != row["evidence_top1_hit"]
            or previous.get("recall_at_3") != row["recall_at_3"]
            or previous.get("evidence_in_top3") != row["evidence_in_top3"]
            or previous_top != current_top
        ):
            mismatches.append(
                {
                    "query": row["query"],
                    "saved_top1": previous_top,
                    "A_top1": current_top,
                    "saved_failure_class": previous.get("failure_class"),
                    "A_failure_class": row["failure_class"],
                }
            )
    return {"available": True, "top1_or_label_mismatches": mismatches}


def _print_report(report: dict) -> None:
    print(f"模型 {report['embedding_model']}，切片 {report['chunk_count']}，维度 {report['dimension']}")
    print("A 组输入 chunk.content；B 组输入 chunk.section + 换行 + chunk.content")
    for group in ("A", "B"):
        item = report["groups"][group]
        print(
            f"{group}：精确 Top-1 {item['exact_top1_hits']}/{item['relevant_count']}，"
            f"精确 Recall@3 {item['recall_at_3']}/{item['relevant_count']}，"
            f"证据 Top-1 {item['evidence_top1_hits']}/{item['relevant_count']}，"
            f"证据 Recall@3 {item['evidence_recall_at_3_hits']}/{item['relevant_count']}"
        )
        for threshold in item["threshold_comparison"]:
            print(
                f"  {group} 阈值 {threshold['max_distance']}: "
                f"无答案误接受 {threshold['unanswerable_false_accepts']}/{item['irrelevant_count']}"
            )
    print(f"Top-1 章节发生变化的题目：{len(report['top1_changes'])}")
    for change in report["top1_changes"]:
        print(
            f"  {change['query']}：A {change['A_top1']}（{change['A_failure_class']}）"
            f" -> B {change['B_top1']}（{change['B_failure_class']}）"
        )
    baseline = report["baseline_comparison"]
    print(f"A 组命中指标与所述基线一致：{str(baseline['A_label_metrics_match_stated_baseline']).lower()}")
    saved = baseline["saved_production_report"]
    if saved["available"]:
        print(f"A 组与已保存生产评测的 Top-1 或命中类别差异：{len(saved['top1_or_label_mismatches'])}")
    print(report["conclusion_limit"])


if __name__ == "__main__":
    raise SystemExit(main())
