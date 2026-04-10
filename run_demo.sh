#!/usr/bin/env bash
# Full pipeline demo: Reddit KB → themes → embed → candidates → Opsera HITL
# Run from: Reddit-Devops-Agent/
#   chmod +x run_demo.sh && ./run_demo.sh

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
KB_DIR="$SCRIPT_DIR/KB"
CLASSIFIER_DIR="$SCRIPT_DIR/Classifier"

PYTHON="/Users/rahulnadkarni/.pyenv/versions/3.10.15/bin/python3"
KB_PYTHON="$PYTHON"
CLASSIFIER_PYTHON="$PYTHON"

THEMES_JSON="$KB_DIR/data/themes/themes.json"
CANDIDATES_JSON="$CLASSIFIER_DIR/candidates_from_themes.json"
ACTION_PLAN_JSON="$CLASSIFIER_DIR/action_plan.json"

# ── helpers ──────────────────────────────────────────────────────────────────

header() { echo; echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"; echo "  $1"; echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"; }

# ── Stage 1: Reddit KB ───────────────────────────────────────────────────────

header "Stage 1 — Show dummy Reddit posts"
"$KB_PYTHON" - <<'EOF'
import json
from pathlib import Path
posts_path = Path(__file__).parent / "data/raw/posts.jsonl" if False else Path("KB/data/raw/posts.jsonl")
posts = [json.loads(l) for l in posts_path.read_text().splitlines() if l.strip()]
print(f"  {len(posts)} posts loaded from r/devops, r/kubernetes, r/docker, r/terraform, r/aws\n")
for p in posts[:6]:
    print(f"  r/{p['subreddit']:12}  {p['title'][:65]}")
print("  ...")
EOF

# ── Stage 2: Extract themes with LLM ─────────────────────────────────────────

header "Stage 2 — Extract community themes with LLM  (reddit-kb-themes)"
cd "$KB_DIR"
"$KB_PYTHON" -c "from reddit_kb.cli import themes_main; themes_main()"
cd "$SCRIPT_DIR"

# ── Stage 3: Embed themes into Chroma ────────────────────────────────────────

header "Stage 3 — Embed themes into vector DB  (reddit-kb-embed)"
cd "$KB_DIR"
"$KB_PYTHON" -c "from reddit_kb.cli import embed_main; embed_main()"
cd "$SCRIPT_DIR"

# ── Stage 4: Show extracted themes ───────────────────────────────────────────

header "Stage 4 — Themes extracted from Reddit"
"$KB_PYTHON" - <<'EOF'
import json
from pathlib import Path
data = json.loads(Path("KB/data/themes/themes.json").read_text())
print(f"  {data['theme_count']} themes found\n")
for t in data["themes"]:
    print(f"  [{t['pain_point_type']:15}]  {t['theme_label']}")
EOF

# ── Stage 5: Bridge — themes → classifier candidates ─────────────────────────

header "Stage 5 — Convert themes → classifier candidates"
"$CLASSIFIER_PYTHON" "$CLASSIFIER_DIR/make_candidates.py" \
  "$THEMES_JSON" \
  --out "$CANDIDATES_JSON"

# ── Stage 6: Index Opsera product KB ─────────────────────────────────────────

header "Stage 6 — Index Opsera product KB  (opsera-ingest)"
cd "$CLASSIFIER_DIR"
"$CLASSIFIER_PYTHON" -m opsera_classifier.ingest
cd "$SCRIPT_DIR"

# ── Stage 7: HITL classifier ─────────────────────────────────────────────────

header "Stage 7 — HITL classifier: score & review  (opsera-hitl)"
echo "  Scoring Reddit themes against Opsera KB..."
echo "  At the prompt:"
echo "    y          → accept the top-3 plan"
echo "    swap S R   → put candidate R into slot S, then re-review"
echo "    n          → abort"
echo

cd "$CLASSIFIER_DIR"
"$CLASSIFIER_PYTHON" -m opsera_classifier.hitl \
  "$CANDIDATES_JSON" \
  --top-n 10 \
  --llm \
  --output "$ACTION_PLAN_JSON"
cd "$SCRIPT_DIR"

# ── Stage 8: Show action plan ────────────────────────────────────────────────

header "Stage 8 — Action plan written"
"$CLASSIFIER_PYTHON" - <<'EOF'
import json
from pathlib import Path
plan = json.loads(Path("Classifier/action_plan.json").read_text())
print(f"  Timestamp: {plan['timestamp']}\n")
for i, c in enumerate(plan["selected_candidates"]):
    print(f"  Slot {i+1}  score={c['similarity']:.3f}")
    print(f"         {c['text'][:110]}...")
    print()
EOF

echo "  Full plan → Classifier/action_plan.json"
echo
