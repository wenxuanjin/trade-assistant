"""用真实 Embeddings 评测本地知识检索。普通单元测试不会运行本脚本。

在 python-agent 目录、并且已经重建索引后执行：

    python scripts/evaluate_retrieval.py

可接受章节按知识正文的业务语义人工标注，不从检索结果反推。
本脚本只报告排序和候选阈值，不修改 EMBEDDING_MAX_DISTANCE，也不重建索引。
"""

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.config import settings
from app.rag.embeddings import create_ollama_embeddings, embedding_model_id
from app.rag.retriever import DEFAULT_INDEX_DIR, retrieve

# section 是精确预期章节。acceptable_sections 是足以回答该问题的章节。
# 父章节只有在自己的正文已经回答问题时才列入，不按层级自动加入。
CASES = [
    {
        "query": "待处理是什么意思",
        "section": "订单状态定义 / 待处理",
        "acceptable_sections": ["订单状态定义 / 待处理"],
        "relevant": True,
    },
    {
        "query": "订单已经创建但还没发货，应该叫什么状态",
        "section": "订单状态定义 / 待处理",
        "acceptable_sections": ["订单状态定义 / 待处理"],
        "relevant": True,
    },
    {
        "query": "已发货代表什么",
        "section": "订单状态定义 / 已发货",
        "acceptable_sections": ["订单状态定义 / 已发货"],
        "relevant": True,
    },
    {
        "query": "货已经交给承运方，但买家可能还没收到",
        "section": "订单状态定义 / 已发货",
        "acceptable_sections": ["订单状态定义 / 已发货"],
        "relevant": True,
    },
    {
        "query": "怎样才算已送达",
        "section": "订单状态定义 / 已送达",
        "acceptable_sections": ["订单状态定义 / 已送达"],
        "relevant": True,
    },
    {
        "query": "没有送达记录时，能不能说用户已经收到货",
        "section": "订单状态定义 / 已送达",
        "acceptable_sections": ["订单状态定义 / 已送达"],
        "relevant": True,
    },
    {
        "query": "订单号在系统里不存在时怎么回复",
        "section": "订单状态定义 / 查无此单",
        "acceptable_sections": ["订单状态定义 / 查无此单"],
        "relevant": True,
    },
    {
        "query": "查不到这笔订单，能不能编造物流",
        "section": "订单状态定义 / 查无此单",
        "acceptable_sections": ["订单状态定义 / 查无此单"],
        "relevant": True,
    },
    {
        "query": "订单状态能不能代替退款结论",
        "section": "订单状态定义",
        "acceptable_sections": ["订单状态定义"],
        "relevant": True,
    },
    {
        "query": "用户问为什么还没送达，第一步要核对什么",
        "section": "发货后未送达的排查流程 / 核对订单是否已发货",
        # 父章节正文写明：先区分订单是否已经发货。
        "acceptable_sections": [
            "发货后未送达的排查流程 / 核对订单是否已发货",
            "发货后未送达的排查流程",
        ],
        "relevant": True,
    },
    {
        "query": "订单还是待处理，能不能按运输延误来解释",
        "section": "发货后未送达的排查流程 / 核对订单是否已发货",
        "acceptable_sections": ["发货后未送达的排查流程 / 核对订单是否已发货"],
        "relevant": True,
    },
    {
        "query": "订单已经发货后应该查看什么",
        "section": "发货后未送达的排查流程 / 查看物流轨迹",
        # 父章节正文写明发货后的下一步是查看轨迹。
        "acceptable_sections": [
            "发货后未送达的排查流程 / 查看物流轨迹",
            "发货后未送达的排查流程",
        ],
        "relevant": True,
    },
    {
        "query": "没有物流轨迹时能不能假设正在派送",
        "section": "发货后未送达的排查流程 / 查看物流轨迹",
        "acceptable_sections": ["发货后未送达的排查流程 / 查看物流轨迹"],
        "relevant": True,
    },
    {
        "query": "物流轨迹还在更新说明什么",
        "section": "发货后未送达的排查流程 / 按轨迹结果处理 / 轨迹仍在更新",
        "acceptable_sections": ["发货后未送达的排查流程 / 按轨迹结果处理 / 轨迹仍在更新"],
        "relevant": True,
    },
    {
        "query": "包裹还在运输途中，回复时应该怎么说",
        "section": "发货后未送达的排查流程 / 按轨迹结果处理 / 轨迹仍在更新",
        "acceptable_sections": ["发货后未送达的排查流程 / 按轨迹结果处理 / 轨迹仍在更新"],
        "relevant": True,
    },
    {
        "query": "物流信息长时间没有变化怎么处理",
        "section": "发货后未送达的排查流程 / 按轨迹结果处理 / 轨迹长时间无更新",
        "acceptable_sections": ["发货后未送达的排查流程 / 按轨迹结果处理 / 轨迹长时间无更新"],
        "relevant": True,
    },
    {
        "query": "轨迹停滞能不能说成即将送达",
        "section": "发货后未送达的排查流程 / 按轨迹结果处理 / 轨迹长时间无更新",
        "acceptable_sections": ["发货后未送达的排查流程 / 按轨迹结果处理 / 轨迹长时间无更新"],
        "relevant": True,
    },
    {
        "query": "还没发货的订单能不能退款",
        "section": "退款处理规则 / 未发货退款",
        "acceptable_sections": ["退款处理规则 / 未发货退款"],
        "relevant": True,
    },
    {
        "query": "未出库的退款要不要先等物流轨迹",
        "section": "退款处理规则 / 未发货退款",
        "acceptable_sections": ["退款处理规则 / 未发货退款"],
        "relevant": True,
    },
    {
        "query": "货已经发出但买家还没收到，退款前要做什么",
        "section": "退款处理规则 / 已发货但未送达",
        "acceptable_sections": ["退款处理规则 / 已发货但未送达"],
        "relevant": True,
    },
    {
        "query": "能不能跳过物流轨迹直接承诺已经退回",
        "section": "退款处理规则 / 已发货但未送达",
        "acceptable_sections": ["退款处理规则 / 已发货但未送达"],
        "relevant": True,
    },
    {
        "query": "货已经送达之后怎么处理退款",
        "section": "退款处理规则 / 已送达后退款",
        # 已发货但未送达是另一种业务情形，不能当作本题证据。
        "acceptable_sections": ["退款处理规则 / 已送达后退款"],
        "relevant": True,
    },
    {
        "query": "送达后还能不能按运输途中丢失来拦截",
        "section": "退款处理规则 / 已送达后退款",
        "acceptable_sections": ["退款处理规则 / 已送达后退款"],
        "relevant": True,
    },
    {"query": "今天的天气怎么样", "section": None, "relevant": False},
    {"query": "怎么修改收货地址", "section": None, "relevant": False},
    {"query": "会员积分怎么兑换", "section": None, "relevant": False},
    {"query": "发票税号填在哪里", "section": None, "relevant": False},
]

CANDIDATE_THRESHOLDS = (0.25, 0.5, 0.75, 1.0, 1.25, 1.5, 2.0)
SEPARABILITY_DEFINITION = (
    "对每条相关问题，取 Top-3 里距离最近的可接受章节；"
    "对每条无答案问题，取 Top-1 距离。"
    "全部相关问题都有可接受证据，且最近可接受距离的最大值小于无答案问题 Top-1 距离的最小值时为 true。"
    "该判断包含证据 Top-1 失败但 Top-3 中仍有可接受章节的题目，不表示生产阈值已经校准。"
)
EVIDENCE_METRIC_NOTE = (
    "evidence_top1_accuracy 和 evidence_recall_at_3 是根据人工标注的可接受章节计算的检索代理指标，"
    "不是最终语言模型回答正确率。"
)
THRESHOLD_NOTE = (
    "候选阈值只过滤本次已经返回的 Top-3 距离，不重新排序，也不能把第二名提升为第一名。"
    "因此精确 Top-1 与证据 Top-1 是否成立，仍取决于原始第一名是否落在对应章节集合内。"
)


def main() -> int:
    _validate_cases()
    model_id = embedding_model_id(settings.embedding_provider, settings.embedding_model)
    try:
        embeddings = create_ollama_embeddings(
            settings.embedding_provider,
            settings.embedding_model,
            settings.embedding_base_url,
        )
        rows = [_evaluate_case(case, embeddings, model_id) for case in CASES]
    except Exception as exc:
        print(f"检索评测失败（{type(exc).__name__}）", file=sys.stderr)
        return 1

    relevant = [row for row in rows if row["relevant"]]
    irrelevant = [row for row in rows if not row["relevant"]]
    exact_top1_hits = sum(row["exact_top1_hit"] for row in relevant)
    evidence_top1_hits = sum(row["evidence_top1_hit"] for row in relevant)
    exact_recall_at_3 = sum(row["recall_at_3"] for row in relevant)
    evidence_recall_at_3_hits = sum(row["evidence_in_top3"] for row in relevant)
    relevant_count = len(relevant)
    irrelevant_count = len(irrelevant)
    thresholds = _threshold_report(relevant, irrelevant)
    separable = _separable(relevant, irrelevant)
    report = {
        "embedding_model": model_id,
        "distance_metric": "squared_l2",
        "question_count": len(rows),
        "relevant_count": relevant_count,
        "irrelevant_count": irrelevant_count,
        "top1_hits": exact_top1_hits,
        "top1_hit_rate": exact_top1_hits / relevant_count,
        "exact_top1_hits": exact_top1_hits,
        "exact_top1_accuracy": exact_top1_hits / relevant_count,
        "recall_at_3": exact_recall_at_3,
        "recall_at_3_rate": exact_recall_at_3 / relevant_count,
        "evidence_top1_hits": evidence_top1_hits,
        "evidence_top1_accuracy": evidence_top1_hits / relevant_count,
        "evidence_recall_at_3_hits": evidence_recall_at_3_hits,
        "evidence_recall_at_3": evidence_recall_at_3_hits / relevant_count,
        "evidence_metric_note": EVIDENCE_METRIC_NOTE,
        "threshold_note": THRESHOLD_NOTE,
        "threshold_comparison": thresholds,
        "distance_ranges_are_separable": separable,
        "separability_definition": SEPARABILITY_DEFINITION,
        "max_distance_calibrated": False,
        "calibration_note": "这一批评测题不能确定生产阈值。EMBEDDING_MAX_DISTANCE 保持未配置。",
        "cases": rows,
    }
    output = ROOT / "data" / "retrieval-eval" / "report.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    _print_report(report, relevant_count, irrelevant_count)
    return 0


def _validate_cases() -> None:
    relevant = [case for case in CASES if case["relevant"]]
    irrelevant = [case for case in CASES if not case["relevant"]]
    if len(CASES) != 27 or len(relevant) != 23 or len(irrelevant) != 4:
        raise RuntimeError("评测题数量与当前基线不一致")
    for case in relevant:
        acceptable = case.get("acceptable_sections")
        if not acceptable or case["section"] not in acceptable:
            raise RuntimeError(f"相关问题缺少包含精确章节的可接受集合：{case['query']}")
    for case in irrelevant:
        if case["section"] is not None or "acceptable_sections" in case:
            raise RuntimeError(f"无答案问题不应设置预期或可接受章节：{case['query']}")
    by_query = {case["query"]: case for case in CASES}
    first = by_query["用户问为什么还没送达，第一步要核对什么"]
    if set(first["acceptable_sections"]) != {
        "发货后未送达的排查流程 / 核对订单是否已发货",
        "发货后未送达的排查流程",
    }:
        raise RuntimeError("第一条偏差的可接受章节不正确")
    second = by_query["货已经送达之后怎么处理退款"]
    if second["acceptable_sections"] != ["退款处理规则 / 已送达后退款"]:
        raise RuntimeError("第二条偏差不能接受其他退款章节")


def _evaluate_case(case: dict, embeddings, model_id: str) -> dict:
    result = retrieve(
        case["query"],
        embeddings,
        index_dir=DEFAULT_INDEX_DIR,
        top_k=3,
        max_distance=1e9,
        expected_embedding_model=model_id,
    )
    hits = [
        {"section": hit.section, "distance": hit.distance, "chunk_id": hit.chunk_id}
        for hit in result.hits
    ]
    expected = case["section"]
    acceptable = case.get("acceptable_sections")
    top_section = hits[0]["section"] if hits else None
    exact_top1_hit = bool(hits) and top_section == expected
    evidence_top1_hit = bool(acceptable) and bool(hits) and top_section in acceptable
    exact_in_top3 = bool(expected) and any(hit["section"] == expected for hit in hits)
    evidence_in_top3 = bool(acceptable) and any(hit["section"] in acceptable for hit in hits)
    failure_class, failure_reason = _classify(
        case["relevant"],
        exact_top1_hit,
        evidence_top1_hit,
        evidence_in_top3,
    )
    return {
        "query": case["query"],
        "expected_section": expected,
        "acceptable_sections": acceptable,
        "relevant": case["relevant"],
        "status": result.status.value,
        "top1_hit": exact_top1_hit if case["relevant"] else False,
        "exact_top1_hit": exact_top1_hit if case["relevant"] else False,
        "evidence_top1_hit": evidence_top1_hit if case["relevant"] else False,
        "recall_at_3": exact_in_top3 if case["relevant"] else False,
        "evidence_in_top3": evidence_in_top3 if case["relevant"] else False,
        "failure_class": failure_class,
        "failure_reason": failure_reason,
        "hits": hits,
        "message": result.message,
    }


def _classify(
    relevant: bool,
    exact_top1_hit: bool,
    evidence_top1_hit: bool,
    evidence_in_top3: bool,
) -> tuple[str, str]:
    if not relevant:
        return "unanswerable", "无答案问题，不参与证据命中。"
    if exact_top1_hit:
        return "exact_hit", "Top-1 与精确章节一致。"
    if evidence_top1_hit:
        return "evidence_only", "Top-1 不是精确章节，但属于可接受证据。"
    if evidence_in_top3:
        return "acceptable_not_top1", "Top-1 不在可接受章节中；可接受证据出现在 Top-3。"
    return "no_acceptable_evidence", "Top-3 没有可接受证据。"


def _threshold_report(relevant: list[dict], irrelevant: list[dict]) -> list[dict]:
    report = []
    relevant_count = len(relevant)
    irrelevant_count = len(irrelevant)
    for threshold in CANDIDATE_THRESHOLDS:
        exact_top1 = 0
        evidence_top1 = 0
        for row in relevant:
            kept = [hit for hit in row["hits"] if hit["distance"] <= threshold]
            if not kept:
                continue
            if kept[0]["section"] == row["expected_section"]:
                exact_top1 += 1
            if kept[0]["section"] in row["acceptable_sections"]:
                evidence_top1 += 1
        false_accepts = sum(
            any(hit["distance"] <= threshold for hit in row["hits"]) for row in irrelevant
        )
        report.append(
            {
                "max_distance": threshold,
                "exact_top1": exact_top1,
                "exact_top1_rate": exact_top1 / relevant_count,
                "evidence_top1": evidence_top1,
                "evidence_top1_rate": evidence_top1 / relevant_count,
                "unanswerable_false_accepts": false_accepts,
                "unanswerable_false_accept_rate": false_accepts / irrelevant_count,
                "relevant_top1": exact_top1,
                "irrelevant_false_hits": false_accepts,
            }
        )
    return report


def _separable(relevant: list[dict], irrelevant: list[dict]) -> bool:
    positive_distances: list[float] = []
    for row in relevant:
        acceptable = row["acceptable_sections"]
        distances = [hit["distance"] for hit in row["hits"] if hit["section"] in acceptable]
        if not distances:
            return False
        positive_distances.append(min(distances))
    negative_distances = [row["hits"][0]["distance"] for row in irrelevant if row["hits"]]
    if not positive_distances or len(negative_distances) != len(irrelevant):
        return False
    return max(positive_distances) < min(negative_distances)


def _print_report(report: dict, relevant_count: int, irrelevant_count: int) -> None:
    print(
        f"评测问题 {report['question_count']}，"
        f"精确 Top-1 {report['exact_top1_hits']}/{relevant_count}，"
        f"精确 Recall@3 {report['recall_at_3']}/{relevant_count}"
    )
    print(
        f"证据 Top-1 {report['evidence_top1_hits']}/{relevant_count}，"
        f"证据 Recall@3 {report['evidence_recall_at_3_hits']}/{relevant_count}"
    )
    print(report["evidence_metric_note"])
    print("阈值对比（候选值，不是生产配置）：")
    for item in report["threshold_comparison"]:
        print(
            f"  {item['max_distance']}: "
            f"精确 Top-1 {item['exact_top1']}/{relevant_count}，"
            f"证据 Top-1 {item['evidence_top1']}/{relevant_count}，"
            f"无答案误接受 {item['unanswerable_false_accepts']}/{irrelevant_count}"
        )
    print(report["threshold_note"])
    print(
        "distance_ranges_are_separable: "
        f"{str(report['distance_ranges_are_separable']).lower()}"
    )
    print(report["separability_definition"])
    print(report["calibration_note"])
    for query in (
        "用户问为什么还没送达，第一步要核对什么",
        "货已经送达之后怎么处理退款",
    ):
        row = next(item for item in report["cases"] if item["query"] == query)
        print(
            f"{row['query']}：{row['failure_class']}，"
            f"精确 Top-1 {row['exact_top1_hit']}，证据 Top-1 {row['evidence_top1_hit']}"
        )


if __name__ == "__main__":
    raise SystemExit(main())
