# template-ai-harness

Template repository for setting up projects with an AI harness. It ships a
small, project-local workflow layer that helps AI coding agents start sessions,
stay scoped to one feature, run verification, record progress, and hand work off
cleanly between sessions.

> Starting a new project from this template? Just start an agent session —
> the harness detects the unconfigured project and guides the agent through
> setup step by step (`./AGENTS.sh init`).

## Quick start

Use the root wrapper for all harness operations:

```sh
./AGENTS.sh help
./AGENTS.sh init
./AGENTS.sh verify
./AGENTS.sh handoff
```

`AGENTS.sh` finds an available Python interpreter and forwards every argument to
the stdlib-only harness CLI in `.agents/agents.py`. Agents and humans should use
the wrapper instead of reaching into `.agents/` directly; the implementation and
state there are harness internals.

## What's inside

```
AGENTS.sh                  Public harness entrypoint; forwards to .agents/agents.py
AGENTS.md                  Agent operating manual — the single manual
CLAUDE.md -> AGENTS.md     Claude Code entrypoint (symlink)
GEMINI.md -> AGENTS.md     Gemini CLI entrypoint (symlink)
.github/
├── copilot-instructions.md  GitHub Copilot entrypoint (points to AGENTS.md)
└── workflows/agents.yml   CI plus optional 10-minute PR automation
.claude/
├── settings.json          SessionStart hook (auto-runs ./AGENTS.sh init) + permissions
└── skills -> .agents/skills   Skill auto-discovery for Claude Code
.agents/
├── README.md              Map of harness internals + design principles
├── agents.py              Harness CLI + optional PR automation; use ./AGENTS.sh help
├── agents.json            All durable state: commands, features, progress log, rules, settings
├── agents.scratch.json    Transient scratch (gitignored; last verify result)
└── skills/
    └── new-skill/         How to author new skills (projects grow their own)
```

## One wrapper guides the workflow

`./AGENTS.sh` is the stable interface. It abstracts away the `.agents/` folder,
selects `python3` or `python`, and delegates to the harness CLI. The CLI then
tells the agent what to do next at every step.

| Subcommand | Job |
|---|---|
| `init` | Session start: on a fresh project it walks guided setup step by step; otherwise health check, skills index, rule counts, git status, current feature, recent progress, and a concrete next step |
| `verify` | Definition of done: runs registered `--verify` commands in order and records the result |
| `handoff` | End-of-session checklist with live status: verify fresh? progress logged? feature closed? committed? pushed? |
| `docs` | Live project docs: a repo map generated from `git ls-files` (never drifts) + curated rules for architecture, conventions, and testing |
| `maintenance` | Upkeep sweep: flags rule categories to combine/prune, stale rules, blocked features, skills and commands to re-check |
| `cmd set/rm/list`, `run` | Command registry: agents register build/test/lint/dev commands instead of editing harness scripts |
| `feature list/add/start/done/block/note` | Scope tracking; enforces one feature in progress |
| `log`, `progress` | Session log: entries auto-stamped with date, commit, and last verify result |
| `check`, `ci` | Structure validation / the single call CI makes |
| `github automate` | Runs GitHub automations (`auto-merge-pr`, `auto-create-pr`); only works inside GitHub Actions runners |
| `github settings` | GitHub automation settings: `auto-merge-pr` and `auto-create-pr` |

Agents never need to know where state lives or hand-edit JSON. Adding a test
step to a project is `./AGENTS.sh cmd set test "npm test" --verify`, not a
script rewrite. All subcommand documentation lives in `./AGENTS.sh help`, so
the manual never drifts from the tool.

## Optional PR automation

The existing `agents.yml` workflow includes an opt-in automation job that runs only on the 10-minute schedule:

```sh
./AGENTS.sh github settings show
./AGENTS.sh github settings auto-merge-pr --on
./AGENTS.sh github settings auto-merge-pr --notify-on --tags "@jules @codex"
./AGENTS.sh github settings auto-create-pr --repo "org/repo" --on
./AGENTS.sh github automate auto-merge-pr --repo org/repo
```

Settings can be configured from any machine, but `github automate` only works
inside GitHub Actions runners; every `./AGENTS.sh github ...` invocation prints
a reminder of this.

Manual `workflow_dispatch` runs still execute the verify job only. Defaults are safe:
both automations are off, blocked-PR comments are off, tags are empty, and the
auto-create webhook URL defaults to `https://auto-create-pr.bysander.net/?repo={r}`.
When guided setup completes, the harness stores `org/repo` automatically when it
can extract one from `GITHUB_REPOSITORY` or a hosted Git remote URL. The `auto-create-pr`
setting cannot be enabled until both the webhook URL and `org/repo` value are
configured. In the workflow, empty values skip the webhook call.

`auto-merge-pr` merges open PRs with no merge conflicts once CI is green. If a
repo has no CI, it only checks merge conflicts. Failed CI or conflicts can get a
PR comment with configured agent tags. Pending CI waits for the next run.

`auto-create-pr` runs after `auto-merge-pr` (which reports open-PR state even
when merging itself is disabled). If PRs remain open, it stops. If no
PRs remain and `.agents/agents.json` still has open features, it POSTs to the
configured webhook URL with `{r}` / `{repo}` replaced by the configured
repository, sending `Authorization: Bearer <token>`. The token is read from the
environment variable named by the `token_env` setting (default `AUTO_MERGE_PR`,
change via `./AGENTS.sh github settings auto-create-pr --token-env NAME`); if that
variable is empty the webhook call is skipped.

## Project docs that don't rot

Static architecture documents drift from the code. Here the repo map is
generated live (`./AGENTS.sh docs`), and only the part worth curating is
stored: terse rules, added one fact at a time as agents learn them
(`./AGENTS.sh docs add conventions "..."`). The harness tracks rule counts and
age; `./AGENTS.sh maintenance` tells an agent doing an upkeep session exactly
what to combine, prune, or re-validate.

## Works with

| Agent | Entrypoint | Extras |
|---|---|---|
| Claude Code | `CLAUDE.md` (symlink) | SessionStart hook auto-runs `./AGENTS.sh init`; skills auto-discovered |
| OpenAI Codex | `AGENTS.md` (read natively) | — |
| Gemini CLI | `GEMINI.md` (symlink) | — |
| GitHub Copilot | `.github/copilot-instructions.md` | Points to `AGENTS.md` and mirrors core rules for surfaces that cannot open repo files |

One manual, four entrypoints. Agents without hook support run `./AGENTS.sh init`
manually. Either way, init prints a skills index so every agent sees the local
playbooks at session start.

## Design principles

Based on harness-engineering research (OpenAI, Anthropic,
[learn-harness-engineering](https://github.com/walkinglabs/learn-harness-engineering)).

1. **Instructions** — `AGENTS.md` stays short; detail lives in
   `./AGENTS.sh help`, loaded on demand.
2. **State** — one JSON file behind the CLI, so sessions resume without cold
   start and agents can't corrupt state by hand-editing.
3. **Verification** — done means `./AGENTS.sh verify` is green.
4. **Scope** — one feature at a time, tracked by the CLI and committed alone.
5. **Handoff** — end sessions with an explicit checklist, progress log, and
   clean git state.
6. **Maintenance** — generated docs never drift; curated rules are kept small
   by an explicit upkeep loop.
