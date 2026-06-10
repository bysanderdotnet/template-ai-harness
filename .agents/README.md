# .agents/ — harness home

All agent-facing infrastructure lives here. Humans rarely need to look inside.

| Path | What | Lifecycle |
|---|---|---|
| `harness.py` | The harness CLI: session init, verification, feature/progress tracking, command registry. Single source of truth for the workflow | Run constantly; edit rarely (register commands instead) |
| `harness.json` | Registered project commands (build/test/lint/...) | Via `harness.py cmd set/rm`, never hand-edit |
| `docs/` | Deep-dive docs: architecture, conventions, testing, token style | Read on demand, keep current |
| `docs/reference/` | Background reading (research, design rationale) | Rarely changes |
| `skills/` | Task playbooks (`<name>/SKILL.md`) | Add one per recurring task |
| `state/progress.json` | Append-only session log | Via `harness.py log` / `progress`, never hand-edit |
| `state/feature_list.json` | Scope: features + status | Via `harness.py feature ...`, never hand-edit |
| `state/last_verify.json` | Last `verify` result (gitignored scratch) | Written by `harness.py verify`, read by `log` |

`harness.py` subcommands: `init` (health check + skills index + state
snapshot), `verify` (registered definition of done), `check` (structure
validation, CI-safe pre-bootstrap), `feature` (scope), `log`/`progress`
(session log; display bounded, no manual compaction), `cmd`/`run` (command
registry). Stdlib-only Python 3 — no pip dependencies.

`AGENTS.md` (repo root) is the single manual; per-agent entrypoints map to it:
`CLAUDE.md` and `GEMINI.md` are symlinks, Codex reads `AGENTS.md` natively,
and `.github/copilot-instructions.md` points Copilot at it.
`.claude/skills` symlinks to `skills/` so Claude Code auto-discovers them.
`.claude/settings.json` wires a SessionStart hook that auto-runs
`harness.py init` and pre-approves the harness CLI.
`.github/workflows/agents.yml` runs `harness.py check`/`init` and
`harness.py verify` in CI — same gates, enforced remotely.

Design principles (from harness-engineering research, see `docs/reference/`):

- Instructions: short AGENTS.md as table of contents; details here, loaded on demand.
- State: progress + feature list on disk, behind a CLI → sessions resume,
  never cold-start, and agents can't corrupt state files by hand-editing.
- Verification: machine-checkable done; registered commands, not vibes.
- Scope: one feature at a time, explicit feature list.
- Lifecycle: init at start, handoff at end.
