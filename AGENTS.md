# Agent Operating Manual

One tool guides the whole workflow:

    ./agents.sh <command>      # --help explains every command

It walks you through first-time setup, runs session init and verification,
registers project commands, tracks features, records progress — and tells you
the next step at every turn. Trust its output over memory. All harness state
lives behind it; never hand-edit its JSON files.

## Project

- Name:
- Stack: 
- Purpose: 

## Session lifecycle

1. `./agents.sh init` — health check + state snapshot (Claude Code auto-runs
   it at session start). Fix what it reports before features. It says SETUP
   MODE? Run `./agents.sh setup` and follow it step by step.
2. Pick ONE item: user request or the next todo init suggests. Mark it:
   `./agents.sh feature start <id>`.
3. Implement. Stay in scope. Task matches a skill (init lists them, dirs in
   `.agents/skills/`)? Follow the playbook, don't improvise.
4. `./agents.sh verify` — green = done. Red = not done, say so.
5. `./agents.sh handoff` — live checklist (log entry, close feature, commit,
   push). Clear every open item before ending the session.

## Repo map

| Path | What |
|---|---|
| `agents.sh` | Public harness entrypoint — finds Python and forwards to the CLI |
| `.agents/agents.py` | Harness CLI implementation — don't inspect/edit for normal work; use `./agents.sh --help` |
| `.agents/agents.json` | Setup state + registered commands (via `cmd set`) |
| `.agents/state/` | Progress log + feature list (via `log` / `feature`) |
| `.agents/docs/` | Architecture, conventions, testing details |
| `.agents/skills/` | Task playbooks (also via `.claude/skills`) |
| `.claude/settings.json` | Claude Code hook (auto-runs init) + permissions |
| `.github/workflows/agents.yml` | CI: `./agents.sh ci` on push/PR — same gates, enforced remotely |
| `.github/copilot-instructions.md` | GitHub Copilot entrypoint that points back to this manual |
| `CLAUDE.md`, `GEMINI.md` | Symlinks to this file. Codex reads `AGENTS.md` natively |
| `README.md` | Human-facing overview for the template repository |

## Rules

- One feature per session/commit. No drive-by refactors.
- Verification gates completion. No green `./agents.sh verify` run = status "unverified".
- Commands or stack changed? `./agents.sh cmd set ...` + sync the CI toolchain
  block — never edit `.agents/agents.py` for this.
- Repo is source of truth. Decision worth keeping → write it to a file.
- Did a multi-step task that will recur (deploy, release, codegen, migration)?
  Capture it as a skill before handoff — playbook:
  `.agents/skills/new-skill/SKILL.md`. Don't wait to be asked.
- Blocked? Record it (`./agents.sh log ... --blockers "..."`), then stop or ask.
- Treat `.agents/agents.py` and `agents.sh` as harness internals. For usage,
  run `./agents.sh --help` or a subcommand-specific help screen.

## Style

- Agent-to-agent text (log entries, feature notes): terse. See `.agents/docs/token-efficiency.md`.
- Code comments/identifiers: normal, full clarity. Terse style is for agent-to-agent text only.

## Deep dives

- Architecture: `.agents/docs/architecture.md`
- Conventions: `.agents/docs/conventions.md`
- Testing/verification: `.agents/docs/testing.md`
- Token efficiency: `.agents/docs/token-efficiency.md`
