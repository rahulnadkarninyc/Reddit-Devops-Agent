from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    slack_bot_token: str = Field(default="", alias="SLACK_BOT_TOKEN")
    slack_channel_id: str = Field(default="", alias="SLACK_CHANNEL_ID")
    slack_signing_secret: str = Field(default="", alias="SLACK_SIGNING_SECRET")

    queue_path: Path = Field(
        default=Path("/Users/rahulnadkarni/Desktop/opsera-reddit-agent/Reddit-Devops-Agent/Slack-Queue/queue.json"),
        alias="QUEUE_PATH",
    )

    host: str = Field(default="127.0.0.1", alias="HOST")
    port: int = Field(default=8080, alias="PORT")
    min_send_interval_minutes: int = Field(default=15, alias="MIN_SEND_INTERVAL_MINUTES")

    @property
    def slack_configured(self) -> bool:
        return bool(self.slack_bot_token and self.slack_channel_id and self.slack_signing_secret)
