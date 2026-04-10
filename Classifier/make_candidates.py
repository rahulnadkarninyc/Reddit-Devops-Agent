"""
Bridge script: converts reddit-kb themes.json → candidates.json for the Opsera classifier.

Usage:
    python make_candidates.py <path/to/themes.json> [--out candidates.json] [--top N]
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path


def themes_to_candidates(
    themes_path: Path,
    top_n: int | None = None,
) -> list[dict]:
    with themes_path.open(encoding="utf-8") as f:
        data = json.load(f)

    themes = data.get("themes", [])
    if top_n:
        themes = themes[:top_n]

    candidates = []
    for t in themes:
        theme_id = t.get("theme_id", "unknown")
        label = t.get("theme_label", "")
        description = t.get("description", "")
        phrases = t.get("example_question_phrases", [])

        # Build a rich text blob: label + description + representative phrases
        parts = [label]
        if description:
            parts.append(description)
        if phrases:
            parts.append("Example questions: " + "; ".join(phrases[:3]))

        candidates.append({"id": theme_id, "text": " ".join(parts)})

    return candidates


def main() -> None:
    p = argparse.ArgumentParser(description="Convert themes.json → candidates.json")
    p.add_argument("themes", type=Path, help="Path to themes.json")
    p.add_argument(
        "--out",
        type=Path,
        default=Path("candidates.json"),
        help="Output path (default: candidates.json)",
    )
    p.add_argument("--top", type=int, default=None, help="Only use top N themes")
    args = p.parse_args()

    candidates = themes_to_candidates(args.themes, top_n=args.top)
    args.out.write_text(json.dumps(candidates, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"Wrote {len(candidates)} candidates → {args.out}")


if __name__ == "__main__":
    main()
