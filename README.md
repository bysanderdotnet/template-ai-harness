# template-ai-harness

Template repository for projects built with AI coding agents. It ships a
pre-wired **harness**: the structure, state files, CLI, and conventions
that let agents work reliably across sessions.

> Starting a new project from this template? Just start an agent session —
> the harness detects the unconfigured project and guides the agent through
> setup step by step (`python3 .agents/agents.py setup`). This README and all
> `TODO(setup)` placeholders get replaced during that setup.

## What's inside

```
AGENTS.md                  Agent operating manual — the single manual
CLAUDE.md -> AGENTS.md     Claude Code entrypoint (symlink)
GEMINI.md -> AGENTS.md     Gemini CLI entrypoint (symlink)
.github/
├── copilot-instructions.md  GitHub Copilot entrypoint (points to AGENTS.md)
└── workflows/agents.yml   CI: `agents.py ci` on push/PR
.claude/
├── settings.json          SessionStart hook (auto-runs agents.py init) + permissions
└── skills -> .agents/skills   Skill auto-discovery for Claude Code
.agents/
├── README.md              Map of the harness + design principles
├── agents.py              The harness CLI — one script guides the whole workflow
├── agents.json            Setup progress + registered project commands
├── docs/
│   ├── architecture.md    Modules, data flow, decision log   (template)
│   ├── conventions.md     Code style, commits, branches      (template)
│   ├── testing.md         How to run/write tests             (template)
│   ├── token-efficiency.md  Terse "caveman" style rules      (ready to use)
│   └── reference/         Distilled harness-engineering research + sources
├── skills/
│   ├── bootstrap-project/ Pointer to guided setup (`agents.py setup`)
│   ├── session-handoff/   Pointer to the handoff checklist (`agents.py handoff`)
│   └── new-skill/         How to author new skills
└── state/
    ├── progress.json      Append-only session log (via `agents.py log`)
    └── feature_list.json  Scope contract (via `agents.py feature ...`)
```

## One script guides the workflow

`python3 .agents/agents.py` (stdlib-only Python 3, no pip installs) is the
single source of truth agents interact with. It doesn't just run things — it
tells the agent what to do next at every step:

| Subcommand | Job |
|---|---|
| `setup` | Guided first-time configuration: shows status and full instructions for the current step only; steps with automatic checks complete themselves; final gates run automatically |
| `init` | Session start: health check, skills index, git status, current feature, recent progress — ends with a concrete `next:` suggestion. Auto-reports issues (broken state, open blockers, missing verify commands) |
| `verify` | Definition of done: runs registered `--verify` commands in order; records the result |
| `handoff` | End-of-session checklist with live status: verify fresh? progress logged? feature closed? committed? pushed? |
| `cmd set/rm/list`, `run` | Command registry: agents *register* build/test/lint/dev commands instead of editing scripts |
| `feature list/add/start/done/block` | Scope tracking; enforces one feature in progress |
| `log`, `progress` | Session log: entries auto-stamped with date, commit, and last verify result; display is bounded so the log never needs manual compaction |
| `check`, `ci` | Structure validation / the single call CI makes |

Agents never need to know where state lives or hand-edit JSON — the script
owns it. Adding a test step to the project is
`agents.py cmd set test "npm test" --verify`, not a script rewrite. All
subcommand documentation lives in `--help`, so the manual never drifts from
the tool.

## Works with

| Agent | Entrypoint | Extras |
|---|---|---|
| Claude Code | `CLAUDE.md` (symlink) | SessionStart hook auto-runs `agents.py init`; skills auto-discovered; harness CLI + read-only git pre-approved |
| OpenAI Codex | `AGENTS.md` (read natively) | — |
| Gemini CLI | `GEMINI.md` (symlink) | — |
| GitHub Copilot | `.github/copilot-instructions.md` | Points to `AGENTS.md` and mirrors its core rules for surfaces that can't open repo files (e.g. code review) |

One manual, four entrypoints. Agents without Claude Code's hook support run
`python3 .agents/agents.py init` manually — the session lifecycle in
`AGENTS.md` instructs them to. Either way, init prints a skills index (name +
description per playbook), so every agent — not just Claude Code with its
skill auto-discovery — sees which playbooks exist at session start.

## Design principles

Based on harness-engineering research (OpenAI, Anthropic,
[learn-harness-engineering](https://github.com/walkinglabs/learn-harness-engineering));
distilled with sources in `.agents/docs/reference/harness-principles.md`.

1. **Instructions** — `AGENTS.md` stays short and links out; detail lives in
   `agents.py --help` and on-demand docs (progressive disclosure). The script
   surfaces the right information at the right time instead of front-loading it.
2. **State** — progress log + feature list live on disk behind the harness
   CLI, so every session resumes instead of cold-starting and no agent
   corrupts state by hand-editing it.
3. **Verification** — `agents.py verify` is the machine-checkable definition
   of done; no green run, no "done". CI runs the same gates on every push/PR,
   so they hold even when an agent forgets.
4. **Scope** — one feature at a time, enforced by `agents.py feature start`.
5. **Lifecycle** — guided `setup` once, `init` at session start (Claude Code
   runs it automatically via a SessionStart hook and gets the state snapshot
   injected into context), `handoff` checklist at session end.

Plus a token-efficiency convention (`.agents/docs/token-efficiency.md`):
agent-to-agent text is written in maximally terse "caveman" style; code and
human-facing docs stay normal.

## Using the template

1. Create a new repo from this template (GitHub: *Use this template*).
2. Start an agent session. With Claude Code: accept the prompt to trust the
   repo's `.claude/settings.json` (it wires the SessionStart hook); the hook
   runs `agents.py init`, which reports SETUP MODE and points at
   `agents.py setup`. With Codex, Gemini CLI, or Copilot: the agent picks up
   the manual via its entrypoint and runs init itself. Either way, the
   script walks the agent through setup (project identity, command
   registration, docs, feature list) and closes it out automatically.
3. From then on, every session follows the lifecycle in `AGENTS.md` — with
   the script suggesting the next step at every turn.
