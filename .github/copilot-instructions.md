# Instructions for GitHub Copilot

Read `AGENTS.md` in the repo root and follow it — it is the agent operating
manual (workflow, repo map, rules). `AGENTS.md` is authoritative; the points
below mirror its core for Copilot surfaces that cannot open repository files.

- One tool drives the workflow: `python3 .agents/harness.py` (init, verify,
  feature, log, cmd, run).
- Session start: `python3 .agents/harness.py init`. Fix environment problems
  before feature work.
- Done means `python3 .agents/harness.py verify` exits 0. No green run, no "done".
- One feature per session/commit. No drive-by refactors.
- State (session log, feature list) is managed through the harness CLI
  (`log`, `progress`, `feature ...`) — never hand-edit `.agents/state/` files.
- Project commands are registered, not hardcoded: `harness.py cmd list` to
  see them, `cmd set <name> "<cmd>" [--verify|--init]` to add one.
