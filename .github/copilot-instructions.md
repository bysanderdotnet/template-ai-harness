# Instructions for GitHub Copilot

Read `AGENTS.md` in the repo root and follow it — it is the agent operating
manual (commands, repo map, session lifecycle, rules). `AGENTS.md` is
authoritative; the points below mirror its core for Copilot surfaces that
cannot open repository files.

- Session start: run `.agents/scripts/init.sh`. Fix environment problems
  before feature work.
- Done means `.agents/scripts/verify.sh` exits 0. No green run, no "done".
- One feature per session/commit. No drive-by refactors.
- State lives in `.agents/state/PROGRESS.md` (session log, append at end) and
  `.agents/state/feature_list.json` (scope, one item at a time).
