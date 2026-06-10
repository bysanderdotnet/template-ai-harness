---
name: session-handoff
description: End-of-session handoff — record progress and close out state so the next session resumes without cold start. Use when wrapping up work, when the user says to stop/pause, or before context runs out.
---

# Session handoff

State on disk beats memory in context. The harness checks the handoff for you.

## Steps

1. Run `python3 .agents/agents.py handoff`. It shows a live checklist:
   verify status, progress entry, feature state, commit, push.
2. Clear every `[..]` item it lists (each one names the exact command).
3. Rerun `handoff` until it reports clean. Never hand off a dirty working
   tree or an unpushed ephemeral session silently.
4. Sweep the "also consider" list it prints: durable decisions →
   `.agents/docs/architecture.md`; recurring procedure → new skill
   (`.agents/skills/new-skill/SKILL.md`); changed commands → `cmd set` + CI.

## Quality bar

Next agent must answer from `agents.py init` output + files alone: what
works, what's broken, what's next, what to not touch. If conversation context
contains a fact needed for that, put it in the log entry now.
