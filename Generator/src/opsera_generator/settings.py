from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


def _default_root() -> Path:
    return Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    openai_api_key: str = Field(default="", alias="OPENAI_API_KEY")
    openai_model: str = Field(default="gpt-4o-mini", alias="OPENAI_MODEL")

    # Inbox: where the Classifier drops pending action plans
    inbox_path: Path = Field(
        default=Path("../Classifier/action_plan_queue/pending"),
        alias="GENERATOR_INBOX_PATH",
    )

    # Output: where the Generator appends Slack queue items
    slack_queue_path: Path = Field(
        default=Path("../Slack-Queue/queue.json"),
        alias="GENERATOR_SLACK_QUEUE_PATH",
    )

    generator_root: Path = Field(default_factory=_default_root, alias="GENERATOR_ROOT")

    def resolve_paths(self) -> "Settings":
        root = Path(self.generator_root)
        if not self.inbox_path.is_absolute():
            object.__setattr__(self, "inbox_path", (root / self.inbox_path).resolve())
        if not self.slack_queue_path.is_absolute():
            object.__setattr__(self, "slack_queue_path", (root / self.slack_queue_path).resolve())
        return self
