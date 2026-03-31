from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


def _default_root() -> Path:
    return Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    reddit_client_id: str = Field(default="", alias="REDDIT_CLIENT_ID")
    reddit_client_secret: str = Field(default="", alias="REDDIT_CLIENT_SECRET")
    reddit_user_agent: str = Field(default="reddit-kb/0.1.0", alias="REDDIT_USER_AGENT")
    # If true, or if client id/secret are unset, ingest uses www.reddit.com/.../*.json only.
    reddit_use_public_json: bool = Field(default=False, alias="REDDIT_USE_PUBLIC_JSON")

    openai_api_key: str = Field(default="", alias="OPENAI_API_KEY")
    openai_model: str = Field(default="gpt-4o-mini", alias="OPENAI_MODEL")
    openai_embedding_model: str = Field(
        default="text-embedding-3-small", alias="OPENAI_EMBEDDING_MODEL"
    )

    reddit_kb_root: Path = Field(default_factory=_default_root, alias="REDDIT_KB_ROOT")
    chroma_path: Path = Field(default=Path("data/chroma"), alias="CHROMA_PATH")
    raw_posts_path: Path = Field(default=Path("data/raw/posts.jsonl"), alias="RAW_POSTS_PATH")

    def resolve_paths(self) -> "Settings":
        root = Path(self.reddit_kb_root)
        if not self.raw_posts_path.is_absolute():
            object.__setattr__(self, "raw_posts_path", root / self.raw_posts_path)
        if not self.chroma_path.is_absolute():
            object.__setattr__(self, "chroma_path", root / self.chroma_path)
        return self
