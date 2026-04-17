from __future__ import annotations

import argparse
import json
import logging
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .models import ActionPlan, Candidate, ScoredCandidate
from .score import score_all
from .settings import Settings

log = logging.getLogger(__name__)


def _load_candidates(path: Path) -> list[Candidate]:
    """Read a JSON file of candidates.
    Expected shape: [{"id": "t3_abc", "text": "How do I set up Jenkins pipelines?"}]
    """
    with path.open(encoding="utf-8") as f:
        raw: list[dict[str, Any]] = json.load(f)
    return [Candidate(id=str(r["id"]), text=str(r["text"])) for r in raw]


def _print_summary(scored: list[ScoredCandidate], top_n: int) -> None:
    """Print a numbered table of the top N candidates for the human to review."""
    print(f"\n{'#':<4} {'Score':<8} {'ID':<14} Preview")
    print("-" * 70)
    for i, c in enumerate(scored[:top_n]):
        preview = c.text[:60].replace("\n", " ")
        print(f"{i + 1:<4} {c.similarity:<8.3f} {c.id:<14} {preview}...")


def _print_plan(plan: list[ScoredCandidate]) -> None:
    """Print the current proposed action plan — the 3 candidates selected."""
    print("\n── Proposed Action Plan ──────────────────────────────────────────")
    for i, c in enumerate(plan):
        print(f"  Slot {i + 1}  [{c.similarity:.3f}]  {c.id}")
        print(f"          {c.text[:100].replace(chr(10), ' ')}...")
    print("──────────────────────────────────────────────────────────────────")


def _prompt_human(top_n_display: list[ScoredCandidate]) -> tuple[str, int, int]:
    """Ask the human what to do with the current plan.

    Returns (action, slot_to_replace, replacement_index) where:
      action = "accept" | "swap" | "abort"
      slot_to_replace = 1-3 (only meaningful on swap)
      replacement_index = 1-N (only meaningful on swap)
    """
    print("\nOptions:")
    print("  y           — accept this plan")
    print("  n           — abort")
    print("  swap S R    — replace slot S (1-3) with candidate R (from the list above)")
    print()

    raw = input("Your choice: ").strip().lower()

    if raw == "y":
        return "accept", 0, 0
    if raw == "n":
        return "abort", 0, 0
    if raw.startswith("swap"):
        parts = raw.split()
        if len(parts) == 3 and parts[1].isdigit() and parts[2].isdigit():
            slot = int(parts[1])
            replacement = int(parts[2])
            if 1 <= slot <= 3 and 1 <= replacement <= len(top_n_display):
                return "swap", slot, replacement
        print("Invalid swap. Use: swap <slot 1-3> <candidate number from list>")
        return "abort", 0, 0

    print("Unrecognised input — aborting.")
    return "abort", 0, 0


def _apply_llm_filter(
    scored: list[ScoredCandidate],
    settings: Settings,
) -> list[ScoredCandidate]:
    """Run llm_classify on each candidate and filter out those the LLM marks as not fit.
    Only called when --llm flag is passed. Preserves original sort order."""
    from .llm_classify import classify

    filtered = []
    for c in scored:
        try:
            result = classify(c, settings)
            if result.get("fit"):
                filtered.append(c)
            else:
                log.info("LLM filtered out %s: %s", c.id, result.get("rationale"))
        except Exception as e:
            log.warning("LLM classify failed for %s: %s — keeping candidate", c.id, e)
            filtered.append(c)
    return filtered


def run_hitl(
    candidates_path: Path,
    settings: Settings,
    top_n: int = 10,
    use_llm: bool = False,
    output_path: Path | None = None,
) -> int:
    settings = settings.resolve_paths()

    candidates = _load_candidates(candidates_path)
    if not candidates:
        log.error("No candidates found in %s", candidates_path)
        return 1
    print(f"\nLoaded {len(candidates)} candidates. Scoring against Opsera KB...")

    scored = score_all(candidates, settings)
    if not scored:
        log.error("Scoring returned no results — is the Opsera Chroma DB built?")
        return 1

    if use_llm:
        print("Running LLM classifier...")
        scored = _apply_llm_filter(scored, settings)
        if not scored:
            print("LLM filtered out all candidates. Nothing to propose.")
            return 1

    _print_summary(scored, top_n)

    plan: list[ScoredCandidate] = list(scored[:3])

    while True:
        _print_plan(plan)
        action, slot, replacement = _prompt_human(scored[:top_n])

        if action == "accept":
            break

        if action == "abort":
            print("Aborted — no action plan written.")
            return 0

        if action == "swap":
            new_candidate = scored[replacement - 1]
            plan[slot - 1] = new_candidate
            print(f"\nSwapped slot {slot} → {new_candidate.id}")

    action_plan = ActionPlan(
        selected_candidates=plan,
        timestamp=datetime.now(timezone.utc),
    )

    out = output_path or Path("action_plan.json")
    out.write_text(
        action_plan.model_dump_json(indent=2),
        encoding="utf-8",
    )
    print(f"\nAction plan written to {out}")

    # Push a copy into the pending queue for the Generator to pick up
    from .queue import push_to_queue

    queue_dir = out.parent / "action_plan_queue"
    queued = push_to_queue(out, queue_dir)
    print(f"Queued for generation → {queued}")

    return 0


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")

    p = argparse.ArgumentParser(description="HITL classifier: score, review, confirm action plan")
    p.add_argument("candidates", type=Path, help="Path to candidates JSON file")
    p.add_argument("--top-n", type=int, default=10, help="How many candidates to display (default 10)")
    p.add_argument("--llm", action="store_true", help="Run LLM classifier as second-pass filter")
    p.add_argument("--output", type=Path, default=None, help="Where to write action_plan.json")
    args = p.parse_args()

    settings = Settings()
    sys.exit(
        run_hitl(
            candidates_path=args.candidates,
            settings=settings,
            top_n=args.top_n,
            use_llm=args.llm,
            output_path=args.output,
        )
    )


if __name__ == "__main__":
    main()
