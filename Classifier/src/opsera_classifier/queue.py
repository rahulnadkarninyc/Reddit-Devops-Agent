"""Push completed action plans into the file-based pending queue."""
from __future__ import annotations

import shutil
from datetime import datetime, timezone
from pathlib import Path


def push_to_queue(action_plan_path: Path, queue_dir: Path) -> Path:
    """Copy a completed action plan into queue_dir/pending/ with a UTC timestamp prefix.

    The original file is left untouched. Returns the path of the queued copy.
    """
    pending_dir = queue_dir / "pending"
    pending_dir.mkdir(parents=True, exist_ok=True)

    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    dest = pending_dir / f"{ts}_plan.json"
    shutil.copy2(action_plan_path, dest)
    return dest
