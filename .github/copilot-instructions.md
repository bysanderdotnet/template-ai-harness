# Instructions for GitHub Copilot

Read `AGENTS.md` in the repo root and follow it — it is the agent operating
manual. `AGENTS.md` is authoritative; the points below mirror its core for
Copilot surfaces that cannot open repository files.

- One tool guides the workflow: `./AGENTS.sh` (`--help` explains every command;
  it suggests the next step at every turn).
- Session start: `./AGENTS.sh init`. It reports SETUP MODE → run
  `./AGENTS.sh setup` and follow it. Fix what init reports before features.
- Done means `./AGENTS.sh verify` exits 0. No green run, no "done".
- Session end: `./AGENTS.sh handoff` — clear every open item.
- One feature per session/commit. No drive-by refactors.
- State (session log, feature list, rules) is managed through the CLI (`log`,
  `feature ...`, `docs ...`) — never hand-edit `.agents/agents.json`.
- Project knowledge: `./AGENTS.sh docs` shows a generated repo map + curated
  rules (architecture / conventions / testing). Read it before coding.
- Project commands are registered, not hardcoded:
  `./AGENTS.sh cmd set <name> "<cmd>" [--verify|--init]`.
- Treat `.agents/agents.py` and `AGENTS.sh` as harness internals; use
  `./AGENTS.sh --help` instead of reading script internals for usage.
