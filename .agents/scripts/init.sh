#!/usr/bin/env bash
# Session-start health check. Run before any feature work.
# Exit 0 = environment healthy. Non-zero = fix environment first.
# Claude Code runs this automatically via the SessionStart hook in .claude/settings.json.
set -euo pipefail
cd "$(git rev-parse --show-toplevel)"

echo "== init: environment check =="

# TEMPLATE: delete this guard during bootstrap.
if [[ -f TEMPLATE_SETUP.md ]]; then
  echo "TEMPLATE_SETUP.md exists: template setup incomplete."
  echo "Complete the checklist in TEMPLATE_SETUP.md before feature work."
  exit 1
fi

echo "-- harness structure --"
ok=1
[[ -L CLAUDE.md ]]                       || { echo "WARN: CLAUDE.md -> AGENTS.md symlink missing"; ok=0; }
[[ -L GEMINI.md ]]                       || { echo "WARN: GEMINI.md -> AGENTS.md symlink missing"; ok=0; }
[[ -f .github/copilot-instructions.md ]] || { echo "WARN: .github/copilot-instructions.md missing"; ok=0; }
[[ -L .claude/skills ]]                  || { echo "WARN: .claude/skills -> .agents/skills symlink missing"; ok=0; }
[[ -f .agents/state/PROGRESS.md ]]       || { echo "WARN: .agents/state/PROGRESS.md missing"; ok=0; }
[[ -f .agents/state/feature_list.json ]] || { echo "WARN: .agents/state/feature_list.json missing"; ok=0; }
if [[ $ok -eq 1 ]]; then echo "structure OK"; fi

echo "-- git status --"
git status --short --branch

echo "-- recent history --"
git log --oneline -5

echo "-- state snapshot --"
if [[ -f .agents/state/PROGRESS.md ]]; then
  # First "## " entry, ignoring headings inside ``` fences (the format example).
  entry="$(awk '/^```/{f=!f} /^## / && !f {n++} n==1' .agents/state/PROGRESS.md)"
  echo "${entry:-PROGRESS.md: no entries yet.}"
fi
if [[ -f .agents/state/feature_list.json ]]; then
  if grep -q '"in_progress"' .agents/state/feature_list.json; then
    echo "feature_list.json in_progress:"
    grep -B 2 '"in_progress"' .agents/state/feature_list.json
  else
    echo "feature_list.json: nothing in_progress."
  fi
fi

# Keep dependency/smoke checks below in sync with the command table in
# AGENTS.md: new tools or dep managers added to the project belong here too.
# TODO(setup): dependency check. Examples:
#   command -v node >/dev/null || { echo "node missing"; exit 1; }
#   [[ -d node_modules ]] || npm ci
#   uv sync --frozen

# TODO(setup): quick smoke check (fast, <30s). Examples:
#   npm run typecheck
#   uv run python -c "import myapp"

echo "== init OK. Pick ONE feature: user request or next todo in feature_list.json. =="
