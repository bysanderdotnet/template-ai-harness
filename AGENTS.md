# Agent Operating Manual

One tool guides the whole workflow:

    python3 .agents/agents.py <command>      # --help explains every command

It walks you through first-time setup, runs session init and verification,
registers project commands, tracks features, records progress — and tells you
the next step at every turn. Trust its output over memory. All harness state
lives behind it; never hand-edit its JSON files.

## Project

<!-- TODO(setup): 2-4 lines. What this project is, main language/stack, target runtime. -->
- Name:
- Stack:
- Purpose:

## Session lifecycle

1. `python3 .agents/agents.py init` — health check + state snapshot (Claude
   Code auto-runs it at session start). Fix what it reports before features.
   It says SETUP MODE? Run `agents.py setup` and follow it step by step.
2. Pick ONE item: user request or the next todo init suggests. Mark it:
   `agents.py feature start <id>`.
3. Implement. Stay in scope. Task matches a skill (init lists them, dirs in
   `.agents/skills/`)? Follow the playbook, don't improvise.
4. `python3 .agents/agents.py verify` — green = done. Red = not done, say so.
5. `python3 .agents/agents.py handoff` — live checklist (log entry, close
   feature, commit, push). Clear every open item before ending the session.

## Repo map

| Path | What |
|---|---|
| `.agents/agents.py` | The harness CLI — start with `--help` |
| `.agents/agents.json` | Setup state + registered commands (via `cmd set`) |
| `.agents/state/` | Progress log + feature list (via `log` / `feature`) |
| `.agents/docs/` | Architecture, conventions, testing details |
| `.agents/skills/` | Task playbooks (also via `.claude/skills`) |
| `.claude/settings.json` | Claude Code hook (auto-runs init) + permissions |
| `.github/workflows/agents.yml` | CI: `agents.py ci` on push/PR — same gates, enforced remotely |
| `CLAUDE.md`, `GEMINI.md` | Symlinks to this file. Codex reads `AGENTS.md` natively; Copilot via `.github/copilot-instructions.md` |
| <!-- TODO(setup): src dirs --> | |

## Rules

- One feature per session/commit. No drive-by refactors.
- Verification gates completion. No green `agents.py verify` run = status "unverified".
- Commands or stack changed? `agents.py cmd set ...` + sync the CI toolchain
  block — never edit `agents.py` for this.
- Repo is source of truth. Decision worth keeping → write it to a file.
- Did a multi-step task that will recur (deploy, release, codegen, migration)?
  Capture it as a skill before handoff — playbook:
  `.agents/skills/new-skill/SKILL.md`. Don't wait to be asked.
- Blocked? Record it (`agents.py log ... --blockers "..."`), then stop or ask.
- <!-- TODO(setup): project-specific no-go zones, e.g. "never edit /migrations" -->

## Style

- Agent-to-agent text (log entries, feature notes): terse. See `.agents/docs/token-efficiency.md`.
- Code comments/identifiers: normal, full clarity. Terse style is for agent-to-agent text only.

## Deep dives

- Architecture: `.agents/docs/architecture.md`
- Conventions: `.agents/docs/conventions.md`
- Testing/verification: `.agents/docs/testing.md`
- Token efficiency: `.agents/docs/token-efficiency.md`
