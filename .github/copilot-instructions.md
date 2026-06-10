# Instructions for GitHub Copilot

Read `AGENTS.md` in the repo root and follow it — it is the agent operating
manual. `AGENTS.md` is authoritative; the points below mirror its core for
Copilot surfaces that cannot open repository files.

- One tool guides the workflow: `./agents.sh` (`--help` explains every command;
  it suggests the next step at every turn).
- Session start: `./agents.sh init`. It reports SETUP MODE → run
  `./agents.sh setup` and follow it. Fix what init reports before features.
- Done means `./agents.sh verify` exits 0. No green run, no "done".
- Session end: `./agents.sh handoff` — clear every open item.
- One feature per session/commit. No drive-by refactors.
- State (session log, feature list) is managed through the CLI (`log`,
  `feature ...`) — never hand-edit `.agents/` JSON files.
- Project commands are registered, not hardcoded:
  `./agents.sh cmd set <name> "<cmd>" [--verify|--init]`.
- Treat `.agents/agents.py` and `agents.sh` as harness internals; use
  `./agents.sh --help` instead of reading script internals for usage.
