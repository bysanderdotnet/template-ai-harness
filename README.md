# template-ai-harness

Template repository for projects built with AI coding agents. It ships a
pre-wired **harness**: the structure, state files, CLI, and conventions
that let agents work reliably across sessions.

> Starting a new project from this template? Open `TEMPLATE_SETUP.md` and let
> your agent work through it — or just tell the agent: *"bootstrap this
> project"*. This README and all `TODO(setup)` placeholders get replaced
> during setup.

## What's inside

```
AGENTS.md                  Agent operating manual — the single manual
CLAUDE.md -> AGENTS.md     Claude Code entrypoint (symlink)
GEMINI.md -> AGENTS.md     Gemini CLI entrypoint (symlink)
TEMPLATE_SETUP.md          First-session checklist; deleted once setup is done
.github/
├── copilot-instructions.md  GitHub Copilot entrypoint (points to AGENTS.md)
└── workflows/agents.yml   CI: harness check/init + verify on push/PR
.claude/
├── settings.json          SessionStart hook (auto-runs harness init) + permissions
└── skills -> .agents/skills   Skill auto-discovery for Claude Code
.agents/
├── README.md              Map of the harness + design principles
├── harness.py             The harness CLI — one script drives the workflow
├── harness.json           Registered project commands (build/test/lint/...)
├── docs/
│   ├── architecture.md    Modules, data flow, decision log   (template)
│   ├── conventions.md     Code style, commits, branches      (template)
│   ├── testing.md         How to run/write tests             (template)
│   ├── token-efficiency.md  Terse "caveman" style rules      (ready to use)
│   └── reference/         Distilled harness-engineering research + sources
├── skills/
│   ├── bootstrap-project/ Playbook for completing template setup
│   ├── session-handoff/   End-of-session state writing
│   └── new-skill/         How to author new skills
└── state/
    ├── progress.json      Append-only session log (via `harness.py log`)
    └── feature_list.json  Scope contract (via `harness.py feature ...`)
```

## One script drives the workflow

`python3 .agents/harness.py` (stdlib-only Python 3, no pip installs) is the
single source of truth agents interact with:

| Subcommand | Job |
|---|---|
| `init` | Session start: health check, skills index, git status, current feature, recent progress. Auto-reports issues (broken state, open blockers, missing verify commands) |
| `verify` | Definition of done: runs registered `--verify` commands in order; records the result |
| `cmd set/rm/list`, `run` | Command registry: agents *register* build/test/lint/dev commands instead of editing scripts |
| `feature list/add/start/done/block` | Scope tracking; enforces one feature in progress |
| `log`, `progress` | Session log: entries auto-stamped with date, commit, and last verify result; display is bounded so the log never needs manual compaction |
| `check` | Structure validation only (CI-safe before bootstrap) |

Agents never need to know where the state lives or hand-edit JSON — the
script owns it. Adding a test step to the project is
`harness.py cmd set test "npm test" --verify`, not a script rewrite.

## Works with

| Agent | Entrypoint | Extras |
|---|---|---|
| Claude Code | `CLAUDE.md` (symlink) | SessionStart hook auto-runs `harness.py init`; skills auto-discovered; harness CLI + read-only git pre-approved |
| OpenAI Codex | `AGENTS.md` (read natively) | — |
| Gemini CLI | `GEMINI.md` (symlink) | — |
| GitHub Copilot | `.github/copilot-instructions.md` | Points to `AGENTS.md` and mirrors its core rules for surfaces that can't open repo files (e.g. code review) |

One manual, four entrypoints. Agents without Claude Code's hook support run
`python3 .agents/harness.py init` manually — the session lifecycle in
`AGENTS.md` instructs them to. Either way, init prints a skills index (name +
description per playbook), so every agent — not just Claude Code with its
skill auto-discovery — sees which playbooks exist at session start.

## Design principles

Based on harness-engineering research (OpenAI, Anthropic,
[learn-harness-engineering](https://github.com/walkinglabs/learn-harness-engineering));
distilled with sources in `.agents/docs/reference/harness-principles.md`.

1. **Instructions** — `AGENTS.md` stays short and links out; agents load
   detail docs on demand (progressive disclosure).
2. **State** — progress log + feature list live on disk behind the harness
   CLI, so every session resumes instead of cold-starting and no agent
   corrupts state by hand-editing it.
3. **Verification** — `harness.py verify` is the machine-checkable definition
   of done; no green run, no "done". CI runs the same gates on every push/PR,
   so they hold even when an agent forgets.
4. **Scope** — one feature at a time, enforced by `harness.py feature start`.
5. **Lifecycle** — `harness.py init` at session start (Claude Code runs it
   automatically via a SessionStart hook and gets git status + latest progress
   entry injected into context), `session-handoff` skill at session end.

Plus a token-efficiency convention (`.agents/docs/token-efficiency.md`):
agent-to-agent text is written in maximally terse "caveman" style; code and
human-facing docs stay normal.

## Using the template

1. Create a new repo from this template (GitHub: *Use this template*).
2. Start an agent session. With Claude Code: accept the prompt to trust the
   repo's `.claude/settings.json` (it wires the SessionStart hook); the hook
   runs `harness.py init`, which surfaces `TEMPLATE_SETUP.md`. With Codex,
   Gemini CLI, or Copilot: the agent picks up the manual via its entrypoint
   and runs init itself. Either way, the agent completes the checklist
   (register commands, fill docs, seed the feature list).
3. From then on, every session follows the lifecycle in `AGENTS.md`.
