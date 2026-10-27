"""Load settings from environment and .env.

Like application.yml plus @ConfigurationProperties.
"""

from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

# 相对项目根目录解析，不依赖启动时的工作目录
_ENV_FILE = Path(__file__).resolve().parent.parent / ".env"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=_ENV_FILE,
        env_file_encoding="utf-8",
        extra="ignore",
    )

    openai_api_key: str
    openai_base_url: str = "https://api.deepseek.com"
    openai_model: str = "deepseek-v4-flash"
    trade_service_base_url: str = "http://localhost:8080"

    # 本地 Embedding。与上面的聊天模型配置分开，不读取 OpenAI Key。
    embedding_provider: str = "ollama"
    embedding_model: str = "bge-m3"
    embedding_base_url: str = "http://localhost:11434"
    embedding_max_distance: float | None = None


settings = Settings()
