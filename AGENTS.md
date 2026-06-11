# Agent Operating Manual

One tool runs the whole workflow:

    ./AGENTS.sh <command>      # --help lists every command

It guides setup, sessions, scope, verification, progress, project docs — and
prints the next step at every turn. Trust its output over memory. All state
lives in `.agents/agents.json`, owned by the CLI — never hand-edit it.

## Project

- Name:
- Stack:
- Purpose:

## Session lifecycle

1. `./AGENTS.sh init` — auto-runs at session start. Fix FAILs before feature
   work. Says SETUP MODE → run `./AGENTS.sh setup`, follow the steps.
2. Pick ONE item: user request or next todo. `./AGENTS.sh feature start <id>`.
3. Implement. Stay in scope. Task matches a skill (init lists them) → follow
   the playbook, don't improvise.
4. `./AGENTS.sh verify` — green = done. Red = not done, say so.
5. `./AGENTS.sh handoff` — clear every open item before ending the session.

## Rules

- One feature per session/commit. No drive-by refactors.
- No green `verify` = status "unverified". Never claim done without it.
- Project knowledge (architecture, conventions, testing) lives behind
  `./AGENTS.sh docs`: generated repo map + curated rules. Read before coding.
  Learned a durable fact → `./AGENTS.sh docs add <category> "<rule>"`.
- Commands or stack changed → `./AGENTS.sh cmd set ...` + sync the CI
  toolchain block in `.github/workflows/agents.yml`.
- Did a recurring multi-step task (deploy, release, migration)? Capture a
  skill — playbook: `.agents/skills/new-skill/SKILL.md`. Don't wait to be asked.
- Blocked → `./AGENTS.sh log ... --blockers "..."`, then stop or ask.
- Asked to do upkeep → `./AGENTS.sh maintenance` lists what to check and prune.
- `AGENTS.sh` / `.agents/agents.py` are harness internals. Usage = `--help`,
  not reading source.

## Style: caveman

Agent-to-agent text — log entries, feature notes, rules — max terse. Tokens
cost; filler carries zero information.

- Drop filler ("I have successfully", "in order to"). Fragments fine:
  "Tests green. Lint: 2 unused imports."
- Exact paths, commands, numbers. "3 failures", not "several issues". Never
  paraphrase a name.
- Say once. Omit what the reader can derive.

Code, comments, commits, user-facing prose: normal clarity. NEVER caveman.
