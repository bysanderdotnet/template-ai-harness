# Agent Operating Manual

Short map, not encyclopedia. Read linked docs only when needed.

<!-- TEMPLATE: If TEMPLATE_SETUP.md exists in repo root, STOP and complete it first. -->

## Project

<!-- TODO(setup): 2-4 lines. What this project is, main language/stack, target runtime. -->
- Name:
- Stack:
- Purpose:

## Commands

Run from repo root. Never claim "done" without `verify.sh` passing.

| Action | Command |
|---|---|
| Session start | `.agents/scripts/init.sh` |
| Full verification | `.agents/scripts/verify.sh` |
| Build | <!-- TODO(setup) --> |
| Test | <!-- TODO(setup) --> |
| Lint | <!-- TODO(setup) --> |
| Typecheck | <!-- TODO(setup) --> |
| Run dev | <!-- TODO(setup) --> |

## Repo map

| Path | What |
|---|---|
| `.agents/` | Harness home: docs, scripts, skills, state |
| `.agents/docs/` | Architecture, conventions, testing details |
| `.agents/state/PROGRESS.md` | Session log. Read at start, update at end |
| `.agents/state/feature_list.json` | Scope. Work on one item at a time |
| `.agents/skills/` | Task playbooks (also via `.claude/skills`) |
| `.claude/settings.json` | Claude Code hooks (auto-runs `init.sh`) + script permissions |
| `CLAUDE.md`, `GEMINI.md` | Symlinks to this file (Claude Code, Gemini CLI). Codex reads `AGENTS.md` natively |
| `.github/copilot-instructions.md` | Copilot entrypoint: points here, mirrors core rules |
| <!-- TODO(setup): src dirs --> | |

## Session lifecycle

1. Read this file + `.agents/state/PROGRESS.md`.
2. Run `.agents/scripts/init.sh` (Claude Code auto-runs it at session start —
   check its output before rerunning). Fix env problems before features.
3. Pick ONE item: user request or next `feature_list.json` item.
4. Implement. Stay in scope.
5. Run `.agents/scripts/verify.sh`. Green = done. Red = not done, say so.
6. Update `PROGRESS.md` + `feature_list.json`. Commit per feature.

## Rules

- One feature per session/commit. No drive-by refactors.
- Verification gates completion. No verify run = status "unverified".
- Repo is source of truth. Decision worth keeping → write it to a file.
- Blocked? Log blocker in `PROGRESS.md`, then stop or ask.
- <!-- TODO(setup): project-specific no-go zones, e.g. "never edit /migrations" -->

## Style

- Output and state files: terse. See `.agents/docs/token-efficiency.md`.
- Code comments/identifiers: normal, full clarity. Terse style is for agent-to-agent text only.

## Deep dives

- Architecture: `.agents/docs/architecture.md`
- Conventions: `.agents/docs/conventions.md`
- Testing/verification: `.agents/docs/testing.md`
- Token efficiency: `.agents/docs/token-efficiency.md`
