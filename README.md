# template-ai-harness

Template repository for setting up projects with an AI harness. It ships a
small, project-local workflow layer that helps AI coding agents start sessions,
stay scoped to one feature, run verification, record progress, and hand work off
cleanly between sessions.

## Quick start

Use the root wrapper for all harness operations:

```sh
./agents.sh --help
./agents.sh init
./agents.sh verify
./agents.sh handoff
```

`agents.sh` finds an available Python interpreter and forwards every argument to
the stdlib-only harness CLI in `.agents/agents.py`. Agents and humans should use
the wrapper instead of reaching into `.agents/` directly; the implementation and
state files there are intended to be harness internals.

## What's inside

```
agents.sh                  Public harness entrypoint; forwards to .agents/agents.py
AGENTS.md                  Agent operating manual — the single manual
CLAUDE.md -> AGENTS.md     Claude Code entrypoint (symlink)
GEMINI.md -> AGENTS.md     Gemini CLI entrypoint (symlink)
.github/
├── copilot-instructions.md  GitHub Copilot entrypoint (points to AGENTS.md)
└── workflows/agents.yml   CI: ./agents.sh ci on push/PR
.claude/
├── settings.json          SessionStart hook (auto-runs ./agents.sh init) + permissions
└── skills -> .agents/skills   Skill auto-discovery for Claude Code
.agents/
├── README.md              Map of harness internals + design principles
├── agents.py              Harness CLI implementation; use ./agents.sh --help
├── agents.json            Setup progress + registered project commands
├── docs/
│   ├── architecture.md    Modules, data flow, decision log
│   ├── conventions.md     Code style, commits, branches
│   ├── testing.md         How to run/write tests
│   ├── token-efficiency.md  Terse style rules for agent-to-agent state
│   └── reference/         Distilled harness-engineering research + sources
├── skills/
│   ├── bootstrap-project/ Pointer to guided setup (./agents.sh setup)
│   ├── session-handoff/   Pointer to the handoff checklist (./agents.sh handoff)
│   └── new-skill/         How to author new skills
└── state/
    ├── progress.json      Append-only session log (via ./agents.sh log)
    └── feature_list.json  Scope contract (via ./agents.sh feature ...)
```

## One wrapper guides the workflow

`./agents.sh` is the stable interface. It abstracts away the `.agents/` folder,
selects `python3` or `python`, and delegates to the harness CLI. The CLI then
tells the agent what to do next at every step.

| Subcommand | Job |
|---|---|
| `setup` | Guided first-time configuration: shows status and current step instructions; final gates run automatically |
| `init` | Session start: health check, skills index, git status, current feature, recent progress, and a concrete next step |
| `verify` | Definition of done: runs registered `--verify` commands in order and records the result |
| `handoff` | End-of-session checklist with live status: verify fresh? progress logged? feature closed? committed? pushed? |
| `cmd set/rm/list`, `run` | Command registry: agents register build/test/lint/dev commands instead of editing harness scripts |
| `feature list/add/start/done/block` | Scope tracking; enforces one feature in progress |
| `log`, `progress` | Session log: entries auto-stamped with date, commit, and last verify result |
| `check`, `ci` | Structure validation / the single call CI makes |

Agents never need to know where state lives or hand-edit JSON. Adding a test
step to a project is `./agents.sh cmd set test "npm test" --verify`, not a
script rewrite. All subcommand documentation lives in `--help`, so the manual
never drifts from the tool.

## Works with

| Agent | Entrypoint | Extras |
|---|---|---|
| Claude Code | `CLAUDE.md` (symlink) | SessionStart hook auto-runs `./agents.sh init`; skills auto-discovered |
| OpenAI Codex | `AGENTS.md` (read natively) | — |
| Gemini CLI | `GEMINI.md` (symlink) | — |
| GitHub Copilot | `.github/copilot-instructions.md` | Points to `AGENTS.md` and mirrors core rules for surfaces that cannot open repo files |

One manual, four entrypoints. Agents without hook support run `./agents.sh init`
manually. Either way, init prints a skills index so every agent sees the local
playbooks at session start.

## Design principles

Based on harness-engineering research (OpenAI, Anthropic,
[learn-harness-engineering](https://github.com/walkinglabs/learn-harness-engineering));
distilled with sources in `.agents/docs/reference/harness-principles.md`.

1. **Instructions** — `AGENTS.md` stays short and links out; detail lives in
   `./agents.sh --help` and docs loaded on demand.
2. **State** — progress, features, commands, and setup state live on disk behind
   the CLI, so sessions resume without cold start.
3. **Verification** — done means `./agents.sh verify` is green.
4. **Scope** — one feature at a time, tracked by the CLI and committed alone.
5. **Handoff** — end sessions with an explicit checklist, progress log, and
   clean git state.
