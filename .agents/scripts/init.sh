#!/usr/bin/env bash
# Session-start health check. Run before any feature work.
# Exit 0 = environment healthy. Non-zero = fix environment first.
set -euo pipefail
cd "$(git rev-parse --show-toplevel)"

echo "== init: environment check =="

if [[ -f TEMPLATE_SETUP.md ]]; then
  echo "TEMPLATE_SETUP.md exists: template setup incomplete."
  echo "Complete the checklist in TEMPLATE_SETUP.md before feature work."
  exit 1
fi

echo "-- git status --"
git status --short --branch

echo "-- recent history --"
git log --oneline -5

# TODO(setup): dependency check. Examples:
#   command -v node >/dev/null || { echo "node missing"; exit 1; }
#   [[ -d node_modules ]] || npm ci
#   uv sync --frozen

# TODO(setup): quick smoke check (fast, <30s). Examples:
#   npm run typecheck
#   uv run python -c "import myapp"

echo "== init OK. Next: read .agents/state/PROGRESS.md, pick ONE feature. =="
