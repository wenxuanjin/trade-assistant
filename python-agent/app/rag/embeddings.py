"""本地 Embedding。

只创建客户端，不在导入或构造时访问 Ollama。
建索引和查询都使用这里返回的同一个 Embeddings 对象，不再额外改写文本。
"""

from langchain_ollama import OllamaEmbeddings

SUPPORTED_PROVIDER = "ollama"


class EmbeddingConfigError(ValueError):
    """Embedding 配置缺失或不被支持。消息中不包含密钥。"""


def embedding_model_id(provider: str, model: str) -> str:
    return f"{provider.strip()}/{model.strip()}"


def create_ollama_embeddings(provider: str, model: str, base_url: str) -> OllamaEmbeddings:
    provider = provider.strip()
    model = model.strip()
    base_url = base_url.strip().rstrip("/")
    if not provider or not model or not base_url:
        raise EmbeddingConfigError("Embedding 未配置，无法执行知识检索。")
    if provider != SUPPORTED_PROVIDER:
        raise EmbeddingConfigError(f"不支持的 Embedding 提供方：{provider}")
    # 本地服务不走系统 HTTP 代理，避免 localhost 被代理改写。
    return OllamaEmbeddings(
        model=model,
        base_url=base_url,
        client_kwargs={"trust_env": False},
    )
