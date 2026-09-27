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


settings = Settings()
