from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


def _default_root() -> Path:
    return Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    openai_api_key: str = Field(default="", alias="OPENAI_API_KEY")
    opsera_kb_root: Path = Field(default_factory=_default_root, alias="OPSERA_KB_ROOT")
    opsera_chroma_path: Path = Field(default=Path("data/chroma"), alias="OPSERA_CHROMA_PATH")
    openai_model: str = Field(default="gpt-4o-mini", alias="OPENAI_MODEL")
    openai_embedding_model: str = Field(default="text-embedding-3-small", alias="OPENAI_EMBEDDING_MODEL")

    def resolve_paths(self) -> "Settings":
        root = Path(self.opsera_kb_root)
        if not self.opsera_chroma_path.is_absolute():
            object.__setattr__(self, "opsera_chroma_path", root / self.opsera_chroma_path)
        return self
