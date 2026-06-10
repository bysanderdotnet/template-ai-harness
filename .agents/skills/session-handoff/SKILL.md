---
name: session-handoff
description: End-of-session handoff — record progress and update feature status via harness.py so the next session resumes without cold start. Use when wrapping up work, when the user says to stop/pause, or before context runs out.
---

# Session handoff

State on disk beats memory in context. Next session reads harness state, not
this conversation. All state goes through `python3 .agents/harness.py`.

## Steps

1. Run `python3 .agents/harness.py verify`. The harness records the result;
   `log` picks it up automatically.
2. Record the session:
   `python3 .agents/harness.py log "<title>" --done "..." --next "..."
   [--issues "..."] [--blockers "..."] [--feature F-NNN]`. Caveman style.
   Must cover: what shipped (paths/commits), known issues, next step, blockers.
3. Update feature status: `harness.py feature done <id>` (or
   `feature block <id> --notes "why"`). Started something new mid-session?
   `feature add` + `feature start` so scope stays accurate.
4. Uncommitted work?
   - Coherent + verified → commit (state files included).
   - Half-done → commit on feature branch with `wip:` prefix, note branch via `log`.
   - Remote/ephemeral session (container dies after session) → push after commit, or work is lost.
   - Never hand off dirty working tree silently.
5. New durable decision made this session → one line in
   `.agents/docs/architecture.md` "Key decisions".
6. Skill sweep: did this session repeat a multi-step procedure, or figure out
   non-obvious steps likely to recur? → capture as skill
   (playbook: `.agents/skills/new-skill/SKILL.md`). One-off → skip.
7. Drift sweep: commands/stack changed this session (new build, test, lint
   step; new tool)? → `harness.py cmd set <name> "<cmd>" [--verify|--init]`
   + sync CI toolchain (`.github/workflows/agents.yml`). New src dir → add to
   AGENTS.md repo map. No change → skip.

## Quality bar

Next agent must answer from `harness.py init` output + files alone: what
works, what's broken, what's next, what to not touch. If conversation context
contains a fact needed for that, write it down now.
