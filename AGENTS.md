# Agent Operating Manual

Short map, not encyclopedia. One tool drives the whole workflow:

    python3 .agents/harness.py <command>      # --help lists everything

It runs session init and verification, tracks features and progress, and
holds the registered project commands. All harness state lives behind it —
manage state through the script, never by hand-editing its JSON files.

<!-- TEMPLATE: If TEMPLATE_SETUP.md exists in repo root, STOP and complete it first. -->

## Project

<!-- TODO(setup): 2-4 lines. What this project is, main language/stack, target runtime. -->
- Name:
- Stack:
- Purpose:

## Session lifecycle

1. `python3 .agents/harness.py init` — health check + state snapshot: skills,
   current feature, recent progress (Claude Code auto-runs it at session
   start — check its output before rerunning). Fix env problems before features.
2. Pick ONE item: user request or the next todo shown by init. Mark it:
   `harness.py feature start <id>` (new scope: `feature add "<title>"`).
3. Implement. Stay in scope. Task matches a skill (init lists them, dirs in
   `.agents/skills/`)? Follow the playbook, don't improvise.
4. `python3 .agents/harness.py verify` — runs the registered definition of
   done. Green = done. Red = not done, say so.
5. Hand off: `harness.py log "<title>" --done "..." --next "..."` +
   `harness.py feature done <id>`. Commit per feature.
   Playbook: `.agents/skills/session-handoff/SKILL.md`.

## Project commands

Build/test/lint/dev commands are registered in the harness, not hardcoded
here or in scripts. `harness.py cmd list` shows them; `harness.py run <name>`
runs one. Stack changed (new build/test/lint step, new tool)? Register it —
don't edit the script:

    python3 .agents/harness.py cmd set test "npm test" --verify

`--verify` adds it to the definition of done (run by `verify`, in listed
order, cheap/fast first); `--init` makes it a session-start smoke check.
Update the CI toolchain (`.github/workflows/agents.yml`) in the same commit.

## Repo map

| Path | What |
|---|---|
| `.agents/harness.py` | Harness CLI: init / verify / feature / log / cmd / run |
| `.agents/harness.json` | Registered commands (via `cmd set`, never hand-edit) |
| `.agents/state/` | Progress log + feature list (via `log` / `feature`, never hand-edit) |
| `.agents/docs/` | Architecture, conventions, testing details |
| `.agents/skills/` | Task playbooks (also via `.claude/skills`) |
| `.claude/settings.json` | Claude Code hook (auto-runs init) + permissions |
| `.github/workflows/agents.yml` | CI: harness init + verify on push/PR — same gates, enforced remotely |
| `CLAUDE.md`, `GEMINI.md` | Symlinks to this file. Codex reads `AGENTS.md` natively; Copilot via `.github/copilot-instructions.md` |
| <!-- TODO(setup): src dirs --> | |

## Rules

- One feature per session/commit. No drive-by refactors.
- Verification gates completion. No green `harness.py verify` run = status "unverified".
- Repo is source of truth. Decision worth keeping → write it to a file.
- Did a multi-step task that will recur (deploy, release, codegen, migration)?
  Capture it as a skill before handoff — playbook:
  `.agents/skills/new-skill/SKILL.md`. Don't wait to be asked.
- Blocked? Record it (`harness.py log ... --blockers "..."` and/or
  `feature block <id> --notes "..."`), then stop or ask.
- <!-- TODO(setup): project-specific no-go zones, e.g. "never edit /migrations" -->

## Style

- Agent-to-agent text (log entries, feature notes): terse. See `.agents/docs/token-efficiency.md`.
- Code comments/identifiers: normal, full clarity. Terse style is for agent-to-agent text only.

## Deep dives

- Architecture: `.agents/docs/architecture.md`
- Conventions: `.agents/docs/conventions.md`
- Testing/verification: `.agents/docs/testing.md`
- Token efficiency: `.agents/docs/token-efficiency.md`
