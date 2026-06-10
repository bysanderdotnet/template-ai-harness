# Architecture

## Modules

| Path | Responsibility | Depends on |
|---|---|---|
| `agents.sh` | Public root entrypoint; finds Python and forwards arguments to the harness CLI | POSIX `sh`, `python3` or `python` |
| `.agents/agents.py` | Harness CLI implementation for setup, init, verify, handoff, command registry, feature tracking, and progress logging | Python 3 stdlib, Git |
| `.agents/agents.json` | Harness configuration: setup status and registered commands | Managed by `./agents.sh cmd ...` and `./agents.sh setup` |
| `.agents/state/` | Durable session state: feature list, progress log, last verify scratch file | Managed by `./agents.sh feature`, `log`, `verify`, `handoff` |
| `AGENTS.md` | Agent operating manual and repo map | Symlink targets `CLAUDE.md`, `GEMINI.md`; referenced by Copilot instructions |
| `.agents/skills/` | Reusable task playbooks discovered by agents | Skill `SKILL.md` files |
| `.github/workflows/agents.yml` | Remote verification gate | `./agents.sh ci` |

## Data flow

1. Agent or CI runs `./agents.sh <command>` from the repo root.
2. `agents.sh` resolves the repo-local `.agents/agents.py`, selects `python3`
   then `python`, and forwards the command arguments unchanged.
3. `.agents/agents.py` reads/writes harness-owned JSON state, runs registered
   project commands, and prints the next workflow step.
4. `./agents.sh verify` records the latest verification result for `log` and
   `handoff`; `./agents.sh ci` enforces the same checks remotely.

## Key decisions

Append-only. One line per decision: date, decision, why.

- 2026-06-10 — Root `agents.sh` wrapper over direct `.agents/agents.py` calls — keeps `.agents/` as implementation detail and centralizes Python discovery.
- 2026-06-10 — Stdlib-only Python harness — template must bootstrap without package installs.
- 2026-06-10 — Harness state managed only through CLI commands — prevents agents from corrupting JSON state by hand.
