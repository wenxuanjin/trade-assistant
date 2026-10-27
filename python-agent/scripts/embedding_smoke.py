"""显式检查本地 Ollama 与 bge-m3。普通单元测试不会运行本脚本。

在 python-agent 目录执行：

    python scripts/embedding_smoke.py
"""

import math
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.config import settings
from app.rag.embeddings import create_ollama_embeddings, embedding_model_id
from app.rag.ingest import load_knowledge_chunks
from app.rag.retriever import RetrievalStatus, build_index, retrieve


def _vectors(raw: list[list[float]]) -> list[list[float]]:
    checked: list[list[float]] = []
    for vector in raw:
        if not vector:
            raise RuntimeError("向量为空")
        numbers = [float(value) for value in vector]
        if any(not math.isfinite(number) for number in numbers):
            raise RuntimeError("向量含有非有限数值")
        checked.append(numbers)
    width = len(checked[0])
    if any(len(vector) != width for vector in checked):
        raise RuntimeError("向量维度不一致")
    return checked


def main() -> int:
    model_id = embedding_model_id(settings.embedding_provider, settings.embedding_model)
    try:
        embeddings = create_ollama_embeddings(
            settings.embedding_provider,
            settings.embedding_model,
            settings.embedding_base_url,
        )
        single = _vectors([embeddings.embed_query("订单已发货但买家还没有收到货")])
        batch = _vectors(embeddings.embed_documents(["待处理表示尚未发货", "未发货可以退款"]))
        if len(single[0]) != len(batch[0]):
            raise RuntimeError("单条与批量向量维度不一致")
        chunks = load_knowledge_chunks(ROOT / "knowledge")
        with tempfile.TemporaryDirectory() as directory:
            index_dir = Path(directory)
            stored = build_index(chunks, embeddings, index_dir, embedding_model=model_id)
            found = retrieve(
                "未发货的订单如何退款",
                embeddings,
                index_dir=index_dir,
                top_k=3,
                max_distance=1e9,
                expected_embedding_model=model_id,
            )
        if found.status is not RetrievalStatus.HIT or not found.hits:
            raise RuntimeError("真实索引没有返回知识片段")
        if len(stored) != len(chunks):
            raise RuntimeError("索引切片数量与知识目录不一致")
    except Exception as exc:
        print(f"Embedding smoke test 失败（{type(exc).__name__}）", file=sys.stderr)
        return 1
    print(
        f"Embedding smoke test 通过：模型 {model_id}，维度 {len(single[0])}，"
        f"临时索引切片 {len(stored)}，示例命中 {found.hits[0].section}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
