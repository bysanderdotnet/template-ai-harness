---
name: session-handoff
description: End-of-session handoff — update PROGRESS.md and feature_list.json so the next session resumes without cold start. Use when wrapping up work, when the user says to stop/pause, or before context runs out.
---

# Session handoff

State on disk beats memory in context. Next session reads files, not this conversation.

## Steps

1. Run `.agents/scripts/verify.sh`. Record exact result.
2. Prepend entry to `.agents/state/PROGRESS.md` using its format. Caveman style.
   Must contain: done (paths/commits), verified status, known issues, next step, blockers.
3. PROGRESS.md over 10 entries → move oldest beyond 10 to top of
   `.agents/state/PROGRESS-archive.md` (create if missing). Keeps session-start reads cheap.
4. Update `.agents/state/feature_list.json` statuses. Max one `in_progress`.
5. Uncommitted work?
   - Coherent + verified → commit.
   - Half-done → commit on feature branch with `wip:` prefix, note branch in PROGRESS.md.
   - Never hand off dirty working tree silently.
6. New durable decision made this session → one line in
   `.agents/docs/architecture.md` "Key decisions".

## Quality bar

Next agent must answer from files alone: what works, what's broken, what's next,
what to not touch. If conversation context contains a fact needed for that,
write it down now.
