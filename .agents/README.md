# .agents/ — harness home

All agent-facing infrastructure lives here. Humans rarely need to look inside.

| Path | What | Lifecycle |
|---|---|---|
| `agents.py` | The harness CLI — guides setup, sessions, verification, state. `--help` documents everything | Run constantly; edit rarely (register commands instead) |
| `agents.json` | Setup progress + registered project commands | Via `agents.py setup` / `cmd set`, never hand-edit |
| `docs/` | Deep-dive docs: architecture, conventions, testing, token style | Read on demand, keep current |
| `docs/reference/` | Background reading (research, design rationale) | Rarely changes |
| `skills/` | Task playbooks (`<name>/SKILL.md`) | Add one per recurring task |
| `state/progress.json` | Append-only session log | Via `agents.py log` / `progress`, never hand-edit |
| `state/feature_list.json` | Scope: features + status | Via `agents.py feature ...`, never hand-edit |
| `state/last_verify.json` | Last `verify` result (gitignored scratch) | Written by `agents.py verify`, read by `log`/`handoff` |

`agents.py` is deliberately a guide, not just a runner: `setup` walks
first-time configuration step by step (auto-detecting completed steps),
`init` snapshots state and suggests the next action, `verify` runs the
registered definition of done, `handoff` checks the session is safely
closeable, and every command ends with a `next:` hint. Stdlib-only Python 3 —
no pip dependencies. Subcommand details live in `--help`, nowhere else.

`AGENTS.md` (repo root) is the single manual; per-agent entrypoints map to it:
`CLAUDE.md` and `GEMINI.md` are symlinks, Codex reads `AGENTS.md` natively,
and `.github/copilot-instructions.md` points Copilot at it.
`.claude/skills` symlinks to `skills/` so Claude Code auto-discovers them.
`.claude/settings.json` wires a SessionStart hook that auto-runs
`agents.py init` and pre-approves the harness CLI.
`.github/workflows/agents.yml` runs `agents.py ci` — same gates, enforced
remotely.

Design principles (from harness-engineering research, see `docs/reference/`):

- Instructions: short AGENTS.md as table of contents; details in `--help`
  and docs, loaded on demand.
- State: progress + feature list on disk, behind a CLI → sessions resume,
  never cold-start, and agents can't corrupt state files by hand-editing.
- Verification: machine-checkable done; registered commands, not vibes.
- Scope: one feature at a time, enforced by the CLI.
- Lifecycle: guided setup once, init at start, handoff checklist at end.
