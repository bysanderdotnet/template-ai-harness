# .agents/ — harness home

All agent-facing infrastructure lives here. Humans rarely need to look inside.

| Path | What | Lifecycle |
|---|---|---|
| `docs/` | Deep-dive docs: architecture, conventions, testing, token style | Read on demand, keep current |
| `docs/reference/` | Background reading (research, design rationale) | Rarely changes |
| `scripts/init.sh` | Session-start health check + state snapshot | Every session start (auto via hook) |
| `scripts/verify.sh` | Definition of done: test + lint + typecheck + build | Run before claiming done |
| `skills/` | Task playbooks (`<name>/SKILL.md`) | Add one per recurring task |
| `state/PROGRESS.md` | Append-only session log | Update at session end |
| `state/feature_list.json` | Scope: features + status | Update when status changes |

`.claude/skills` symlinks to `skills/` so Claude Code auto-discovers them.
`CLAUDE.md` (repo root) symlinks to `AGENTS.md` for the same reason.
`.claude/settings.json` wires a SessionStart hook that auto-runs
`scripts/init.sh` and pre-approves both harness scripts.

Design principles (from harness-engineering research, see `docs/reference/`):

- Instructions: short AGENTS.md as table of contents; details here, loaded on demand.
- State: progress + feature list on disk → sessions resume, never cold-start.
- Verification: machine-checkable done; scripts, not vibes.
- Scope: one feature at a time, explicit feature list.
- Lifecycle: init at start, handoff at end.
