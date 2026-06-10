# template-ai-harness

Template repository for projects built with AI coding agents. It ships a
pre-wired **harness**: the structure, state files, scripts, and conventions
that let agents work reliably across sessions.

> Starting a new project from this template? Open `TEMPLATE_SETUP.md` and let
> your agent work through it — or just tell the agent: *"bootstrap this
> project"*. This README and all `TODO(setup)` placeholders get replaced
> during setup.

## What's inside

```
AGENTS.md                  Agent operating manual — the single source of truth
CLAUDE.md -> AGENTS.md     Claude Code entrypoint (symlink)
GEMINI.md -> AGENTS.md     Gemini CLI entrypoint (symlink)
TEMPLATE_SETUP.md          First-session checklist; deleted once setup is done
.github/
├── copilot-instructions.md  GitHub Copilot entrypoint (points to AGENTS.md)
└── workflows/verify.yml   CI: init.sh health check + verify.sh on push/PR (skipped until setup)
.claude/
├── settings.json          SessionStart hook (auto-runs init.sh) + script permissions
└── skills -> .agents/skills   Skill auto-discovery for Claude Code
.agents/
├── README.md              Map of the harness + design principles
├── docs/
│   ├── architecture.md    Modules, data flow, decision log   (template)
│   ├── conventions.md     Code style, commits, branches      (template)
│   ├── testing.md         How to run/write tests             (template)
│   ├── token-efficiency.md  Terse "caveman" style rules      (ready to use)
│   └── reference/         Distilled harness-engineering research + sources
├── scripts/
│   ├── init.sh            Session-start health check + state snapshot
│   └── verify.sh          Definition of done: test/lint/typecheck/build
├── skills/
│   ├── bootstrap-project/ Playbook for completing template setup
│   ├── session-handoff/   End-of-session state writing
│   └── new-skill/         How to author new skills
└── state/
    ├── PROGRESS.md        Append-only session log
    └── feature_list.json  Scope contract: one feature at a time
```

## Works with

| Agent | Entrypoint | Extras |
|---|---|---|
| Claude Code | `CLAUDE.md` (symlink) | SessionStart hook auto-runs `init.sh`; skills auto-discovered; harness scripts + read-only git pre-approved |
| OpenAI Codex | `AGENTS.md` (read natively) | — |
| Gemini CLI | `GEMINI.md` (symlink) | — |
| GitHub Copilot | `.github/copilot-instructions.md` | Points to `AGENTS.md` and mirrors its core rules for surfaces that can't open repo files (e.g. code review) |

One manual, four entrypoints. Agents without Claude Code's hook support run
`.agents/scripts/init.sh` manually — the session lifecycle in `AGENTS.md`
instructs them to.

## Design principles

Based on harness-engineering research (OpenAI, Anthropic,
[learn-harness-engineering](https://github.com/walkinglabs/learn-harness-engineering));
distilled with sources in `.agents/docs/reference/harness-principles.md`.

1. **Instructions** — `AGENTS.md` stays short and links out; agents load
   detail docs on demand (progressive disclosure).
2. **State** — `PROGRESS.md` + `feature_list.json` live on disk, so every
   session resumes instead of cold-starting.
3. **Verification** — `verify.sh` is the machine-checkable definition of
   done; no green run, no "done". CI runs `init.sh` + `verify.sh` on every
   push/PR, so the gates hold even when an agent forgets to.
4. **Scope** — one feature at a time, tracked in `feature_list.json`.
5. **Lifecycle** — `init.sh` at session start (Claude Code runs it
   automatically via a SessionStart hook and gets git status + latest progress
   entry injected into context), `session-handoff` skill at session end.

Plus a token-efficiency convention (`.agents/docs/token-efficiency.md`):
agent-to-agent text is written in maximally terse "caveman" style; code and
human-facing docs stay normal.

## Using the template

1. Create a new repo from this template (GitHub: *Use this template*).
2. Start an agent session. With Claude Code: accept the prompt to trust the
   repo's `.claude/settings.json` (it wires the SessionStart hook); the hook
   runs `init.sh`, which surfaces `TEMPLATE_SETUP.md`. With Codex, Gemini
   CLI, or Copilot: the agent picks up the manual via its entrypoint and
   runs `init.sh` itself. Either way, the agent completes the checklist
   (fill commands, docs, feature list).
3. From then on, every session follows the lifecycle in `AGENTS.md`.
