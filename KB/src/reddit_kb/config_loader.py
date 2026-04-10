from pathlib import Path
from typing import Any

import yaml


def load_yaml(path: Path) -> dict[str, Any]:
    with path.open(encoding="utf-8") as f:
        data = yaml.safe_load(f)
    if not isinstance(data, dict):
        raise ValueError(f"Expected mapping in {path}")
    return data


def subreddit_names(root: Path) -> list[str]:
    cfg = load_yaml(root / "config" / "subreddits.yaml")
    subs = cfg.get("subreddits")
    if not isinstance(subs, list) or not all(isinstance(s, str) for s in subs):
        raise ValueError("config/subreddits.yaml must contain subreddits: [str, ...]")
    return [s.strip().lower().removeprefix("r/") for s in subs]


def ingest_options(root: Path) -> dict[str, Any]:
    return load_yaml(root / "config" / "ingest.yaml")
