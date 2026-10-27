from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

# repo root: src/hosoai/settings.py -> parents[4]
REPO_ROOT = Path(__file__).resolve().parents[4]


class Settings(BaseSettings):
    """Runtime config, read from environment / .env. No provider is hard-coded."""

    # Repo-root .env first; a local apps/api/.env (if any) overrides it.
    model_config = SettingsConfigDict(env_file=(REPO_ROOT / ".env", ".env"), extra="ignore")

    llm_base_url: str = "http://localhost:11434/v1"
    llm_api_key: str = "ollama"
    llm_model: str = "qwen2.5:7b"
    llm_vision_model: str = "qwen2.5vl:7b"
    database_url: str = "sqlite:///./hosoai.db"
    data_dir: Path = REPO_ROOT / "data"
    cors_origins: list[str] = ["http://localhost:3000"]
