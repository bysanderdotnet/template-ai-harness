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
AGENTS.md                  Agent operating manual (short, table-of-contents style)
CLAUDE.md -> AGENTS.md     Symlink so Claude Code picks it up
TEMPLATE_SETUP.md          First-session checklist; deleted once setup is done
.claude/skills -> .agents/skills   Skill auto-discovery for Claude Code
.agents/
├── README.md              Map of the harness + design principles
├── docs/
│   ├── architecture.md    Modules, data flow, decision log   (template)
│   ├── conventions.md     Code style, commits, branches      (template)
│   ├── testing.md         How to run/write tests             (template)
│   ├── token-efficiency.md  Terse "caveman" style rules      (ready to use)
│   └── reference/         Background research on harness engineering
├── scripts/
│   ├── init.sh            Session-start health check
│   └── verify.sh          Definition of done: test/lint/typecheck/build
├── skills/
│   ├── bootstrap-project/ Playbook for completing template setup
│   ├── session-handoff/   End-of-session state writing
│   └── new-skill/         How to author new skills
└── state/
    ├── PROGRESS.md        Append-only session log
    └── feature_list.json  Scope contract: one feature at a time
```

## Design principles

Based on harness-engineering research (OpenAI, Anthropic,
[learn-harness-engineering](https://github.com/walkinglabs/learn-harness-engineering));
full report in `.agents/docs/reference/`.

1. **Instructions** — `AGENTS.md` stays short and links out; agents load
   detail docs on demand (progressive disclosure).
2. **State** — `PROGRESS.md` + `feature_list.json` live on disk, so every
   session resumes instead of cold-starting.
3. **Verification** — `verify.sh` is the machine-checkable definition of
   done; no green run, no "done".
4. **Scope** — one feature at a time, tracked in `feature_list.json`.
5. **Lifecycle** — `init.sh` at session start, `session-handoff` skill at
   session end.

Plus a token-efficiency convention (`.agents/docs/token-efficiency.md`):
agent-to-agent text is written in maximally terse "caveman" style; code and
human-facing docs stay normal.

## Using the template

1. Create a new repo from this template (GitHub: *Use this template*).
2. Start an agent session; it will hit `TEMPLATE_SETUP.md` via `init.sh`
   and complete the checklist (fill commands, docs, feature list).
3. From then on, every session follows the lifecycle in `AGENTS.md`.
