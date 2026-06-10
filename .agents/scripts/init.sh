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
[[ -f AGENTS.md ]]                       || { echo "FAIL: AGENTS.md missing (symlink targets dangle)"; ok=0; }
[[ -L CLAUDE.md ]]                       || { echo "FAIL: CLAUDE.md -> AGENTS.md symlink missing"; ok=0; }
[[ -L GEMINI.md ]]                       || { echo "FAIL: GEMINI.md -> AGENTS.md symlink missing"; ok=0; }
[[ -f .github/copilot-instructions.md ]] || { echo "FAIL: .github/copilot-instructions.md missing"; ok=0; }
[[ -L .claude/skills ]]                  || { echo "FAIL: .claude/skills -> .agents/skills symlink missing"; ok=0; }
[[ -f .agents/state/PROGRESS.md ]]       || { echo "FAIL: .agents/state/PROGRESS.md missing"; ok=0; }
[[ -f .agents/state/feature_list.json ]] || { echo "FAIL: .agents/state/feature_list.json missing"; ok=0; }
if [[ $ok -eq 1 ]]; then echo "structure OK"; fi

echo "-- skills (playbooks in .agents/skills/) --"
for dir in .agents/skills/*/; do
  [[ -d $dir ]] || continue
  name="$(basename "$dir")"
  if [[ -f "${dir}SKILL.md" ]]; then
    desc="$(sed -n 's/^description: //p' "${dir}SKILL.md" | head -1)"
    echo "  ${name}: ${desc:-(no description in frontmatter)}"
  else
    echo "  WARN: ${dir} has no SKILL.md"
  fi
done

echo "-- git status --"
git status --short --branch

echo "-- recent history --"
git log --oneline -5 2>/dev/null || echo "(no commits yet)"

echo "-- state snapshot --"
if [[ -f .agents/state/PROGRESS.md ]]; then
  # First "## " entry, ignoring headings inside ``` fences (the format example).
  entry="$(awk '/^```/{f=!f} /^## / && !f {n++} n==1' .agents/state/PROGRESS.md)"
  echo "${entry:-PROGRESS.md: no entries yet.}"
  # Enforce the compaction policy stated at the top of PROGRESS.md.
  entries="$(awk '/^```/{f=!f} /^## / && !f {n++} END{print n+0}' .agents/state/PROGRESS.md)"
  if (( entries > 10 )); then
    echo "WARN: PROGRESS.md has ${entries} entries (policy: max 10)."
    echo "      Move oldest to .agents/state/PROGRESS-archive.md (see session-handoff skill)."
  fi
fi
if [[ -f .agents/state/feature_list.json ]]; then
  if command -v python3 >/dev/null 2>&1; then
    # Validate JSON + invariants; corrupted state blocks the session.
    python3 - <<'PY' || ok=0
import json, sys
path = ".agents/state/feature_list.json"
try:
    with open(path) as fh:
        data = json.load(fh)
except Exception as e:
    sys.exit(f"FAIL: {path} is not valid JSON: {e}")
feats = data.get("features", [])
def fmt(f): return f"{f.get('id', '?')} — {f.get('title', '?')}"
wip = [f for f in feats if f.get("status") == "in_progress"]
if len(wip) > 1:
    print(f"WARN: {len(wip)} features in_progress (policy: max 1): "
          + ", ".join(f.get("id", "?") for f in wip))
if wip:
    print(f"feature_list.json in_progress: {fmt(wip[0])}")
else:
    todo = [f for f in feats if f.get("status") == "todo"]
    nxt = f" Next todo: {fmt(todo[0])}" if todo else " No todos left."
    print("feature_list.json: nothing in_progress." + nxt)
PY
  else
    # No python3 on this machine: fall back to a cheap grep.
    if grep -q '"in_progress"' .agents/state/feature_list.json; then
      echo "feature_list.json in_progress:"
      grep -B 2 '"in_progress"' .agents/state/feature_list.json
    else
      echo "feature_list.json: nothing in_progress."
    fi
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

if [[ $ok -eq 1 ]]; then
  echo "== init OK. Pick ONE feature: user request or next todo in feature_list.json. =="
else
  echo "== init FAILED: fix the FAILs above before feature work. =="
  exit 1
fi
