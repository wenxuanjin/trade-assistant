"""用当前 Embedding 配置重建本地知识索引。

在 python-agent 目录执行：

    python scripts/build_knowledge_index.py

不会启动 FastAPI，也不会写入距离阈值。
"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.config import settings
from app.rag.embeddings import create_ollama_embeddings, embedding_model_id
from app.rag.ingest import load_knowledge_chunks
from app.rag.retriever import DEFAULT_INDEX_DIR, build_index


def main() -> int:
    model_id = embedding_model_id(settings.embedding_provider, settings.embedding_model)
    try:
        embeddings = create_ollama_embeddings(
            settings.embedding_provider,
            settings.embedding_model,
            settings.embedding_base_url,
        )
        chunks = load_knowledge_chunks(ROOT / "knowledge")
        stored = build_index(
            chunks,
            embeddings,
            DEFAULT_INDEX_DIR,
            embedding_model=model_id,
        )
    except Exception as exc:
        print(f"索引构建失败（{type(exc).__name__}）", file=sys.stderr)
        return 1
    print(f"索引已重建：切片 {len(stored)}，模型 {model_id}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
