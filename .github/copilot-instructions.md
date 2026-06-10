# Instructions for GitHub Copilot

Read `AGENTS.md` in the repo root and follow it — it is the agent operating
manual. `AGENTS.md` is authoritative; the points below mirror its core for
Copilot surfaces that cannot open repository files.

- One tool guides the workflow: `python3 .agents/agents.py` (`--help`
  explains every command; it suggests the next step at every turn).
- Session start: `python3 .agents/agents.py init`. It reports SETUP MODE →
  run `agents.py setup` and follow it. Fix what init reports before features.
- Done means `python3 .agents/agents.py verify` exits 0. No green run, no "done".
- Session end: `python3 .agents/agents.py handoff` — clear every open item.
- One feature per session/commit. No drive-by refactors.
- State (session log, feature list) is managed through the CLI (`log`,
  `feature ...`) — never hand-edit `.agents/` JSON files.
- Project commands are registered, not hardcoded:
  `agents.py cmd set <name> "<cmd>" [--verify|--init]`.
